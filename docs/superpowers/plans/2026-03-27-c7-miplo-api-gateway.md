# Sprint 2c: C7 MIPLO API Gateway — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the processor-facing MIPLO API gateway that validates sub-licensee BICs, threads TenantContext through the LIP pipeline to C6 and C7, and partitions decision log entries by tenant_id — enabling multi-tenant processor deployments (P3 Platform Licensing).

**Architecture:** The MIPLO gateway sits between the processor's HTTP requests and the existing LIP pipeline. `MIPLOService` validates that each payment's `sending_bic` is authorized under the processor's C8 license token, then calls `pipeline.process()` with a `TenantContext` parameter. The pipeline threads `tenant_id` to `_run_c6()` (activating Sprint 2b tenant velocity isolation) and to the `payment_context` dict consumed by C7. C7's `_log_decision()` writes `tenant_id` into every `DecisionLogEntryData` entry — enabling per-tenant audit partitioning. A FastAPI router at `/miplo` exposes `POST /process` and `GET /status` endpoints.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, dataclasses, HMAC-SHA256, pytest

**Sprint Dependencies:**
- Sprint 2a (C8 processor token): `ProcessorLicenseeContext` with `sub_licensee_bics` — DONE
- Sprint 2b (C6 tenant velocity): `AMLChecker.check(tenant_id=...)` — DONE

---

## Context

This is Sprint 2c of the P3 Platform Licensing build (Session 1 = shared infra + C8 processor tokens, Sprint 2b = C6 tenant velocity isolation). The MIPLO gateway is the processor-facing API surface — the contract between a processor (e.g., Finastra) and the LIP platform.

**Why now:** C6 already accepts `tenant_id` (Sprint 2b), C8 already validates processor tokens (Sprint 2a). The missing link is the HTTP API layer that extracts tenant context from the C8 token and threads it through the pipeline to C6 and C7. Without this, processor deployments cannot be multi-tenant-aware.

**What this enables:** After this sprint, a processor container can receive payment events via HTTP, validate BICs against its license, run the full LIP pipeline with tenant-scoped AML velocity, and produce tenant-partitioned decision logs. Sprint 2d can then build multi-tenant settlement tracking on top.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `lip/tests/test_miplo_gateway.py` | TDD tests for all Sprint 2c components |
| Modify | `lip/c7_execution_agent/decision_log.py:57` | Add `tenant_id: str = ""` to DecisionLogEntryData |
| Modify | `lip/c7_execution_agent/agent.py:559-591` | Thread `tenant_id` from payment_context to `_log_decision()` |
| Modify | `lip/pipeline.py:180,350,507,773` | Add `tenant_context` param, thread to `_run_c6()` and `payment_context` |
| Create | `lip/api/miplo_service.py` | MIPLOService — BIC validation, tenant-scoped pipeline execution |
| Create | `lip/api/miplo_router.py` | FastAPI router — POST /miplo/process, GET /miplo/status |
| Modify | `lip/api/app.py:46,163` | Conditionally wire MIPLO router when pipeline + processor context provided |

---

## Task 1: Write TDD Test Suite

All tests written first. Implementation follows in Tasks 2–5.

**Files:**
- Create: `lip/tests/test_miplo_gateway.py`

- [ ] **Step 1: Write the complete test file**

```python
"""
test_miplo_gateway.py — TDD tests for Sprint 2c: C7 MIPLO API Gateway.

Tests cover:
  - DecisionLogEntryData tenant_id field and HMAC integrity
  - Pipeline.process() tenant_context threading to C6 and payment_context
  - MIPLOService BIC validation and tenant-scoped pipeline execution
  - MIPLO router HTTP endpoints
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
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
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_gateway.py -v 2>&1 | head -40`
Expected: Failures from missing `tenant_id` field on DecisionLogEntryData, missing `tenant_context` parameter on `pipeline.process()`, missing `MIPLOService` module.

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_miplo_gateway.py
git commit -m "test(miplo): add TDD test suite for MIPLO gateway, pipeline tenant threading, decision log tenant_id"
```

---

## Task 2: Add tenant_id to Decision Log + C7 Agent Threading

**Files:**
- Modify: `lip/c7_execution_agent/decision_log.py` (line 57)
- Modify: `lip/c7_execution_agent/agent.py` (lines 211–264, 559–591)

- [ ] **Step 1: Add tenant_id field to DecisionLogEntryData**

In `lip/c7_execution_agent/decision_log.py`, add after `licensee_id: str = ""` (line 57), before `entry_signature: str = ""` (line 58):

```python
    tenant_id: str = ""             # P3: processor tenant for per-tenant audit partitioning
```

**CIPHER critical:** This field is automatically included in the HMAC signature because `_entry_to_canonical_json()` (line 108) uses `asdict(entry)` with `d.pop("entry_signature", None)` — all other fields are signed. No change needed to the signing logic.

- [ ] **Step 2: Add tenant_id parameter to C7 _log_decision()**

In `lip/c7_execution_agent/agent.py`, modify the `_log_decision` method signature (line 559). Add `tenant_id: str = ""` as the last parameter before the closing `)`:

Change:
```python
    def _log_decision(
        self,
        uetr: str,
        individual_payment_id: str,
        decision_type: str,
        failure_probability: float,
        pd_score: float,
        fee_bps: int,
        loan_amount: Decimal,
        dispute_class: str,
        aml_passed: bool,
        human_override: bool = False,
    ) -> str:
```

To:
```python
    def _log_decision(
        self,
        uetr: str,
        individual_payment_id: str,
        decision_type: str,
        failure_probability: float,
        pd_score: float,
        fee_bps: int,
        loan_amount: Decimal,
        dispute_class: str,
        aml_passed: bool,
        human_override: bool = False,
        tenant_id: str = "",
    ) -> str:
```

- [ ] **Step 3: Pass tenant_id to DecisionLogEntryData construction**

In the same method body (line 573), add `tenant_id=tenant_id` to the DecisionLogEntryData constructor.

Change:
```python
            licensee_id=self.licensee_id,
        )
```

To:
```python
            licensee_id=self.licensee_id,
            tenant_id=tenant_id,
        )
```

- [ ] **Step 4: Extract tenant_id in process_payment() and pass to all _log_decision() calls**

In `process_payment()` (line 211), add tenant_id extraction IMMEDIATELY after the existing uetr/individual_payment_id extraction — **before** the TPS guard, kill-switch guard, and borrower enrollment guard. After line 222 (`individual_payment_id = payment_context.get("individual_payment_id", "")`), add:

```python
        tenant_id = str(payment_context.get("tenant_id", ""))
```

**CRITICAL:** This MUST be before line 250 (the first `_log_decision()` call inside the borrower enrollment guard). Placing it later will cause `NameError`.

Then update EVERY `self._log_decision(...)` call in `process_payment()` to pass `tenant_id=tenant_id`. There are approximately 10 call sites (lines 250, 270, 278, 294, 344, 360, 393, 414, 428, 448). Each call that currently ends with:
```python
            entry_id = self._log_decision(
                uetr, individual_payment_id, "BLOCK",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
            )
```

Becomes:
```python
            entry_id = self._log_decision(
                uetr, individual_payment_id, "BLOCK",
                failure_prob, pd_score, fee_bps, loan_amount, dispute_class, aml_passed,
                tenant_id=tenant_id,
            )
```

**Important:** Some calls pass `human_override=True` — add `tenant_id=tenant_id` AFTER the `human_override` argument. Do not disturb existing positional arguments.

- [ ] **Step 5: Run decision log + agent tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_gateway.py::TestDecisionLogTenantId lip/tests/test_miplo_gateway.py::TestAgentTenantIdThreading lip/tests/test_c7_execution.py -v`
Expected: All decision log and agent tests PASS. Existing C7 tests still pass (backward compatible).

- [ ] **Step 6: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/c7_execution_agent/`
Expected: zero errors

- [ ] **Step 7: Commit**

```bash
git add lip/c7_execution_agent/decision_log.py lip/c7_execution_agent/agent.py
git commit -m "feat(c7): add tenant_id to DecisionLogEntryData and thread from payment_context"
```

---

## Task 3: Pipeline tenant_context Threading

**Files:**
- Modify: `lip/pipeline.py` (lines 3, 180, 350, 507, 773)

- [ ] **Step 1: Add TenantContext import**

In `lip/pipeline.py`, add to the imports section (after the existing `lip.common` imports near lines 45–54):

```python
from lip.common.schemas import TenantContext
```

Note: Check where existing `lip.common` imports are. The import should be grouped with other `lip.common` imports for ruff isort compliance.

- [ ] **Step 2: Add tenant_context parameter to process()**

Modify the `process()` method signature (line 180). Add `tenant_context: Optional[TenantContext] = None` as the last parameter:

Change:
```python
    def process(
        self,
        event: NormalizedEvent,
        borrower: Optional[dict] = None,
        entity_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
        human_override_decision: Optional[str] = None,
    ) -> PipelineResult:
```

To:
```python
    def process(
        self,
        event: NormalizedEvent,
        borrower: Optional[dict] = None,
        entity_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
        human_override_decision: Optional[str] = None,
        tenant_context: Optional[TenantContext] = None,
    ) -> PipelineResult:
```

- [ ] **Step 3: Extract tenant_id early in process()**

After the `borrower = borrower or {}` line (line 273), add:

```python
        # P3 Platform Licensing: extract tenant_id for C6 velocity isolation and C7 audit
        tenant_id = tenant_context.tenant_id if tenant_context is not None else None
```

- [ ] **Step 4: Thread tenant_id to _run_c6() call**

Modify the C6 submit call (line 350). Change:

```python
            f_c6 = executor.submit(self._run_c6, event, entity_id, beneficiary_id, tracker)
```

To:

```python
            f_c6 = executor.submit(self._run_c6, event, entity_id, beneficiary_id, tracker, tenant_id)
```

- [ ] **Step 5: Add tenant_id to payment_context dict**

In the `payment_context = { ... }` dict (line 507), add after `"anomaly_flagged": anomaly_flagged,` (line 536):

```python
            # P3 Platform Licensing: tenant_id for per-tenant decision log partitioning
            "tenant_id": tenant_id or "",
```

- [ ] **Step 6: Add tenant_id parameter to _run_c6()**

Modify the `_run_c6` method signature (line 773). Add `tenant_id=None` as the last parameter:

Change:
```python
    def _run_c6(
        self,
        event: NormalizedEvent,
        entity_id: str,
        beneficiary_id: str,
        tracker: LatencyTracker,
    ):
```

To:
```python
    def _run_c6(
        self,
        event: NormalizedEvent,
        entity_id: str,
        beneficiary_id: str,
        tracker: LatencyTracker,
        tenant_id: Optional[str] = None,
    ):
```

- [ ] **Step 7: Pass tenant_id to c6.check()**

In the `self._c6.check()` call inside `_run_c6()` (line 808), add `tenant_id=tenant_id`:

Change:
```python
        with tracker.measure("c6"):
            return self._c6.check(
                entity_id, event.amount, beneficiary_id,
                dollar_cap_override=dollar_cap,
                count_cap_override=count_cap,
            )
```

To:
```python
        with tracker.measure("c6"):
            return self._c6.check(
                entity_id, event.amount, beneficiary_id,
                dollar_cap_override=dollar_cap,
                count_cap_override=count_cap,
                tenant_id=tenant_id,
            )
```

- [ ] **Step 8: Run pipeline tenant_context tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_gateway.py::TestPipelineTenantContext -v`
Expected: All 5 tests PASS.

- [ ] **Step 9: Run full E2E pipeline tests (regression)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_e2e_pipeline.py -v`
Expected: All existing E2E tests PASS (backward compatible — tenant_context defaults to None).

- [ ] **Step 10: Run ruff check**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/pipeline.py`
Expected: zero errors

- [ ] **Step 11: Commit**

```bash
git add lip/pipeline.py
git commit -m "feat(pipeline): add tenant_context parameter, thread tenant_id to C6 and C7 payment_context"
```

---

## Task 4: MIPLO Service + Router

**Files:**
- Create: `lip/api/miplo_service.py`
- Create: `lip/api/miplo_router.py`

- [ ] **Step 1: Create MIPLOService**

Create `lip/api/miplo_service.py`:

```python
"""
miplo_service.py — MIPLO API Gateway service layer.
P3 Platform Licensing: validates sub-licensee BICs and threads TenantContext.

The MIPLO (Money In / Payment Lending Organisation) is the processor role
in the P3 three-entity model. This service validates that each payment's
sending_bic is authorized under the processor's C8 license token, then
calls the LIP pipeline with a tenant-scoped TenantContext.
"""
from __future__ import annotations

import logging
from typing import Optional

from lip.c8_license_manager.license_token import ProcessorLicenseeContext
from lip.common.schemas import TenantContext
from lip.infrastructure.monitoring.metrics import (
    METRIC_MIPLO_REQUEST_COUNT,
    METRIC_TENANT_ISOLATION_VIOLATION,
)

logger = logging.getLogger(__name__)


class UnauthorizedBICError(Exception):
    """Raised when a payment's sending_bic is not in the processor's sub_licensee_bics.

    This is a tenant isolation violation — the BIC is not authorized to transact
    through this processor's deployment. Logged as a security event.
    """

    def __init__(self, bic: str, tenant_id: str):
        self.bic = bic
        self.tenant_id = tenant_id
        super().__init__(f"BIC {bic!r} not authorized for tenant {tenant_id!r}")


class MIPLOService:
    """MIPLO API Gateway — validates BICs and threads TenantContext through pipeline.

    Constructed once at container boot from ProcessorLicenseeContext (C8 validated).
    Immutable after construction — TenantContext is frozen.
    """

    def __init__(
        self,
        pipeline,
        processor_context: ProcessorLicenseeContext,
        metrics_collector=None,
    ):
        self._pipeline = pipeline
        self._tenant_id = processor_context.licensee_id
        self._sub_licensee_bics: frozenset[str] = frozenset(processor_context.sub_licensee_bics)
        self._tenant_context = TenantContext(
            tenant_id=self._tenant_id,
            sub_licensee_bics=list(processor_context.sub_licensee_bics),
            deployment_phase=processor_context.deployment_phase,
        )
        self._metrics = metrics_collector

    @property
    def tenant_id(self) -> str:
        """Processor tenant identifier from C8 license token."""
        return self._tenant_id

    @property
    def tenant_context(self) -> TenantContext:
        """Frozen TenantContext for this processor deployment."""
        return self._tenant_context

    def validate_bic(self, sending_bic: str) -> bool:
        """Check if sending_bic is authorized under this processor's license."""
        return sending_bic in self._sub_licensee_bics

    def process_payment(
        self,
        event,
        borrower=None,
        entity_id: Optional[str] = None,
        beneficiary_id: Optional[str] = None,
    ):
        """Run a payment through the tenant-scoped LIP pipeline.

        Validates that event.sending_bic is in the processor's sub_licensee_bics.
        Raises UnauthorizedBICError if not — this is a hard gate, not a soft flag.

        Args:
            event: NormalizedEvent from C5.
            borrower: Optional borrower-level data for C2 PD inference.
            entity_id: Optional entity override for C6 velocity.
            beneficiary_id: Optional beneficiary override for C6 velocity.

        Returns:
            PipelineResult from the tenant-scoped pipeline execution.

        Raises:
            UnauthorizedBICError: If sending_bic not in sub_licensee_bics.
        """
        if not self.validate_bic(event.sending_bic):
            logger.warning(
                "BIC isolation violation: bic=%s tenant=%s",
                event.sending_bic,
                self._tenant_id,
            )
            if self._metrics:
                self._metrics.increment(
                    METRIC_TENANT_ISOLATION_VIOLATION,
                    {"tenant_id": self._tenant_id},
                )
            raise UnauthorizedBICError(event.sending_bic, self._tenant_id)

        if self._metrics:
            self._metrics.increment(METRIC_MIPLO_REQUEST_COUNT)

        return self._pipeline.process(
            event=event,
            borrower=borrower,
            entity_id=entity_id,
            beneficiary_id=beneficiary_id,
            tenant_context=self._tenant_context,
        )

    def get_status(self) -> dict:
        """Return processor container status for the /miplo/status endpoint."""
        return {
            "tenant_id": self._tenant_id,
            "sub_licensee_bics": sorted(self._sub_licensee_bics),
            "deployment_phase": self._tenant_context.deployment_phase,
        }
```

- [ ] **Step 2: Create MIPLO Router**

Create `lip/api/miplo_router.py`:

```python
"""
miplo_router.py — MIPLO API Gateway HTTP endpoints.
P3 Platform Licensing: processor-facing REST API.

Endpoints:
  POST /miplo/process — Submit a payment for tenant-scoped pipeline execution.
  GET  /miplo/status  — Processor container status (tenant info, authorized BICs).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from datetime import datetime, timezone
    from decimal import Decimal

    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    class MIPLOProcessRequest(BaseModel):
        """Payment event submitted by a processor for pipeline execution."""

        uetr: str = Field(..., description="Unique End-to-End Transaction Reference")
        individual_payment_id: str = Field(
            default="", description="ISO 20022 individual payment ID"
        )
        sending_bic: str = Field(..., description="Originator bank BIC")
        receiving_bic: str = Field(..., description="Beneficiary bank BIC")
        amount: str = Field(..., description="Payment amount as Decimal string")
        currency: str = Field(..., description="ISO 4217 currency code")
        rejection_code: str = Field(..., description="ISO 20022 rejection reason code")
        narrative: str = Field(default="", description="Free-text payment narrative")
        debtor_account: str = Field(
            default="", description="Debtor account identifier (IBAN or Othr.Id)"
        )
        borrower: Optional[dict] = Field(
            default=None, description="Borrower-level data for C2 PD inference"
        )
        entity_id: Optional[str] = Field(
            default=None, description="Override entity ID for C6 velocity"
        )
        beneficiary_id: Optional[str] = Field(
            default=None, description="Override beneficiary ID for C6 velocity"
        )

    class MIPLOProcessResponse(BaseModel):
        """Pipeline result scoped to the processor's tenant."""

        outcome: str
        uetr: str
        tenant_id: str
        failure_probability: float
        above_threshold: bool
        loan_offer: Optional[dict] = None
        decision_entry_id: Optional[str] = None
        pd_estimate: Optional[float] = None
        fee_bps: Optional[int] = None
        total_latency_ms: float = 0.0

    def make_miplo_router(miplo_service: Any, auth_dependency=None) -> APIRouter:
        """Factory that builds the MIPLO API router.

        Follows the same pattern as make_admin_router and make_portfolio_router.
        The miplo_service is captured by closure — no global state.
        """
        router = APIRouter(tags=["miplo"])

        if auth_dependency is not None:
            deps = [Depends(auth_dependency)]
        else:
            deps = []

        @router.post("/process", response_model=MIPLOProcessResponse, dependencies=deps)
        async def process_payment(request: MIPLOProcessRequest):
            """Submit a payment event for tenant-scoped LIP pipeline execution.

            The sending_bic must be in the processor's authorized sub_licensee_bics
            (validated via C8 license token). Returns 403 if not authorized.
            """
            from lip.c5_streaming.event_normalizer import NormalizedEvent

            event = NormalizedEvent(
                uetr=request.uetr,
                individual_payment_id=request.individual_payment_id,
                sending_bic=request.sending_bic,
                receiving_bic=request.receiving_bic,
                amount=Decimal(request.amount),
                currency=request.currency,
                timestamp=datetime.now(tz=timezone.utc),
                rail="SWIFT",
                rejection_code=request.rejection_code,
                narrative=request.narrative,
                debtor_account=request.debtor_account or None,
            )

            from lip.api.miplo_service import UnauthorizedBICError

            try:
                result = miplo_service.process_payment(
                    event=event,
                    borrower=request.borrower,
                    entity_id=request.entity_id,
                    beneficiary_id=request.beneficiary_id,
                )
            except UnauthorizedBICError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

            return MIPLOProcessResponse(
                outcome=result.outcome,
                uetr=result.uetr,
                tenant_id=miplo_service.tenant_id,
                failure_probability=result.failure_probability,
                above_threshold=result.above_threshold,
                loan_offer=result.loan_offer,
                decision_entry_id=result.decision_entry_id,
                pd_estimate=result.pd_estimate,
                fee_bps=result.fee_bps,
                total_latency_ms=result.total_latency_ms,
            )

        @router.get("/status", dependencies=deps)
        async def get_status():
            """Return processor container status (tenant info, authorized BICs)."""
            return miplo_service.get_status()

        return router

except ImportError:
    logger.debug("FastAPI not installed — MIPLO router not available")

    def make_miplo_router(*args, **kwargs):  # type: ignore[misc]
        raise ImportError("FastAPI is required for the MIPLO router")
```

- [ ] **Step 3: Run MIPLO service tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_gateway.py::TestMIPLOService -v`
Expected: All 8 tests PASS.

- [ ] **Step 4: Run ruff check on new files**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/api/miplo_service.py lip/api/miplo_router.py`
Expected: zero errors

- [ ] **Step 5: Commit**

```bash
git add lip/api/miplo_service.py lip/api/miplo_router.py
git commit -m "feat(miplo): add MIPLOService (BIC validation + tenant context) and MIPLO router"
```

---

## Task 5: Wire into create_app() + Full Regression

**Files:**
- Modify: `lip/api/app.py` (lines 46, 163)

- [ ] **Step 1: Add optional parameters to create_app()**

In `lip/api/app.py`, modify the `create_app()` function signature (line 46).

Change:
```python
    def create_app() -> FastAPI:
```

To:
```python
    def create_app(pipeline=None, processor_context=None) -> FastAPI:
```

- [ ] **Step 2: Add MIPLO router wiring (before `return application`)**

Before `return application` (line 163), add:

```python
        # MIPLO gateway (P3 processor deployments — conditional)
        if pipeline is not None and processor_context is not None:
            from lip.api.miplo_router import make_miplo_router
            from lip.api.miplo_service import MIPLOService

            miplo_svc = MIPLOService(pipeline, processor_context, metrics_collector)
            application.include_router(
                make_miplo_router(miplo_svc, auth_dependency=auth_dep),
                prefix="/miplo",
            )
```

- [ ] **Step 3: Update the fallback create_app (line 172) for signature consistency**

Change the fallback:
```python
    def create_app():  # type: ignore[misc]
```

To:
```python
    def create_app(pipeline=None, processor_context=None):  # type: ignore[misc]
```

- [ ] **Step 4: Run all Sprint 2c tests**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/test_miplo_gateway.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run full test suite (regression check)**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py -q 2>&1 | tail -20`
Expected: All ~1610+ tests pass (1591 from Sprint 2b + ~19 new), zero failures.

- [ ] **Step 6: Run ruff on entire lip/ directory**

Run: `cd /Users/tomegah/PRKT2026 && PYTHONPATH=. ruff check lip/`
Expected: zero errors

- [ ] **Step 7: Commit**

```bash
git add lip/api/app.py
git commit -m "feat(app): conditionally wire MIPLO gateway when pipeline + processor context provided"
```

---

## Verification Checklist

Before declaring Sprint 2c complete:

1. [ ] `ruff check lip/` — zero errors
2. [ ] `python -m pytest lip/tests/test_miplo_gateway.py -v` — all new tests pass
3. [ ] `python -m pytest lip/tests/test_c7_execution.py -v` — all existing C7 tests pass (backward compat)
4. [ ] `python -m pytest lip/tests/test_e2e_pipeline.py -v` — all E2E tests pass (backward compat)
5. [ ] `python -m pytest lip/tests/ -x --ignore=lip/tests/test_e2e_live.py` — no regressions
6. [ ] Manual: `DecisionLogEntryData.tenant_id` is HMAC-signed (tampering detected)
7. [ ] Manual: `pipeline.process(tenant_context=None)` works identically to before
8. [ ] Manual: `MIPLOService` raises `UnauthorizedBICError` for unauthorized BICs
9. [ ] Manual: No secrets, artifacts/, or c6_corpus_*.json in any committed file

---

## CIPHER / QUANT Review Notes

**CIPHER — Decision Log Integrity:**
`tenant_id` is automatically included in the HMAC signature because `_entry_to_canonical_json()` serialises all fields via `asdict()` minus `entry_signature`. No signing logic change needed. Tampering with `tenant_id` after logging will be detected by `DecisionLogger.verify()`.

**CIPHER — BIC Validation Boundary:**
`MIPLOService.validate_bic()` is the tenant isolation enforcement point. A BIC that passes validation enters the pipeline with tenant-scoped velocity windows (Sprint 2b). The `sub_licensee_bics` frozenset is immutable after construction — derived from the C8 token, which is HMAC-signed.

**CIPHER — Attack Surface Note:**
The MIPLO `/process` endpoint accepts `entity_id` and `beneficiary_id` overrides. In a malicious scenario, a compromised processor could override these to evade velocity checks. This is an acceptable risk because: (1) the processor has already been C8-validated at boot, (2) BIC validation still enforces the tenant boundary, (3) the overrides match the existing pipeline.process() API. If override restriction is required, it's a Sprint 3+ hardening item.

**QUANT — No Fee Logic Changes:**
Sprint 2c does not modify any fee computation, minimum loan amount, or maturity logic. All financial math is untouched. The only QUANT-relevant change is that `tenant_id` appears in decision log entries — this supports per-tenant revenue reconciliation in Sprint 2d.

**NOVA — Pipeline Backward Compatibility:**
`tenant_context=None` (the default) produces identical behaviour to the pre-Sprint 2c pipeline. C6 receives `tenant_id=None` → falls through to existing single-tenant code path. C7 receives `tenant_id=""` → decision log entry has empty tenant_id (same as before). No existing test or production flow is affected.

---

## Next Sprint: 2d (Multi-Tenant Settlement Tracking)

Sprint 2d extends C3 with:
- Per-tenant settlement monitoring (NAVEvent emission every 60 minutes)
- Tenant-scoped portfolio queries (extend portfolio_router.py)
- Revenue metering integration (connect MIPLOService to RevenueMetering on settlement)
