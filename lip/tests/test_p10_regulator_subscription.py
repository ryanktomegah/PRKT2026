"""
test_p10_regulator_subscription.py — Sprint 6 tests for P10/C8 extension.

C8 extension: RegulatorSubscriptionToken + query metering integration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lip.c8_license_manager.query_metering import (
    PrivacyBudgetExceededError,
    QueryBudgetExceededError,
    RegulatoryQueryMetering,
)
from lip.c8_license_manager.regulator_subscription import (
    RegulatorSubscriptionToken,
    decode_regulator_token,
    encode_regulator_token,
    sign_regulator_token,
    verify_regulator_token,
)

_KEY = b"regulator-signing-key-32-bytes!!!!"


def _make_regulator_token(
    subscription_tier: str = "QUERY",
    permitted_corridors: list[str] | None = None,
    query_budget_monthly: int = 100,
    privacy_budget_allocation: float = 5.0,
    valid_for_days: int = 30,
) -> RegulatorSubscriptionToken:
    now = datetime.now(timezone.utc)
    return RegulatorSubscriptionToken(
        regulator_id="OSFI-001",
        regulator_name="OSFI",
        subscription_tier=subscription_tier,
        permitted_corridors=permitted_corridors,
        query_budget_monthly=query_budget_monthly,
        privacy_budget_allocation=privacy_budget_allocation,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=valid_for_days),
    )


class TestRegulatorSubscriptionToken:
    """Token signing/verification and compact encoding tests."""

    def test_sign_verify_roundtrip(self):
        token = _make_regulator_token()
        signed = sign_regulator_token(token, _KEY)
        assert signed.hmac_signature != ""
        assert verify_regulator_token(signed, _KEY)

    def test_tampering_detected(self):
        token = sign_regulator_token(_make_regulator_token(), _KEY)
        tampered = RegulatorSubscriptionToken(
            regulator_id=token.regulator_id,
            regulator_name=token.regulator_name,
            subscription_tier=token.subscription_tier,
            permitted_corridors=["GBP-*"],
            query_budget_monthly=token.query_budget_monthly,
            privacy_budget_allocation=token.privacy_budget_allocation,
            valid_from=token.valid_from,
            valid_until=token.valid_until,
            hmac_signature=token.hmac_signature,
        )
        assert not verify_regulator_token(tampered, _KEY)

    def test_encoded_token_round_trip(self):
        signed = sign_regulator_token(_make_regulator_token(), _KEY)
        encoded = encode_regulator_token(signed)
        decoded = decode_regulator_token(encoded)
        assert decoded.regulator_id == signed.regulator_id
        assert decoded.hmac_signature == signed.hmac_signature
        assert verify_regulator_token(decoded, _KEY)

    def test_expired_token_rejected(self):
        now = datetime.now(timezone.utc)
        expired = RegulatorSubscriptionToken(
            regulator_id="OSFI-001",
            regulator_name="OSFI",
            subscription_tier="QUERY",
            permitted_corridors=None,
            query_budget_monthly=10,
            privacy_budget_allocation=1.0,
            valid_from=now - timedelta(days=10),
            valid_until=now - timedelta(days=1),
        )
        signed = sign_regulator_token(expired, _KEY)
        assert not verify_regulator_token(signed, _KEY)


class TestRegulatoryQueryMetering:
    """Metering and budget enforcement tests."""

    def test_record_query_updates_usage(self):
        token = _make_regulator_token(query_budget_monthly=5, privacy_budget_allocation=1.0)
        meter = RegulatoryQueryMetering(metering_key=_KEY)
        signed = sign_regulator_token(token, _KEY)
        entry = meter.record_query(
            token=signed,
            endpoint="/api/v1/regulatory/metadata",
            corridors_queried=[],
            epsilon_consumed=0.05,
            response_latency_ms=12,
            billing_amount_usd=Decimal("5000"),
        )
        usage = meter.get_usage(signed.regulator_id)
        assert usage["query_count"] == 1
        assert usage["epsilon_consumed"] == pytest.approx(0.05)
        assert len(entry.hmac_signature) == 64

    def test_query_budget_exhaustion_raises(self):
        token = sign_regulator_token(
            _make_regulator_token(query_budget_monthly=1, privacy_budget_allocation=1.0),
            _KEY,
        )
        meter = RegulatoryQueryMetering()
        meter.record_query(
            token=token,
            endpoint="/api/v1/regulatory/metadata",
            corridors_queried=[],
            epsilon_consumed=0.05,
            response_latency_ms=10,
            billing_amount_usd=Decimal("5000"),
        )
        with pytest.raises(QueryBudgetExceededError):
            meter.record_query(
                token=token,
                endpoint="/api/v1/regulatory/metadata",
                corridors_queried=[],
                epsilon_consumed=0.05,
                response_latency_ms=10,
                billing_amount_usd=Decimal("5000"),
            )

    def test_privacy_budget_exhaustion_raises(self):
        token = sign_regulator_token(
            _make_regulator_token(query_budget_monthly=10, privacy_budget_allocation=0.05),
            _KEY,
        )
        meter = RegulatoryQueryMetering()
        meter.record_query(
            token=token,
            endpoint="/api/v1/regulatory/metadata",
            corridors_queried=[],
            epsilon_consumed=0.05,
            response_latency_ms=10,
            billing_amount_usd=Decimal("5000"),
        )
        with pytest.raises(PrivacyBudgetExceededError):
            meter.record_query(
                token=token,
                endpoint="/api/v1/regulatory/metadata",
                corridors_queried=[],
                epsilon_consumed=0.01,
                response_latency_ms=10,
                billing_amount_usd=Decimal("5000"),
            )


class TestRegulatoryRouterWithSubscriptionToken:
    """Regulatory API auth + budget enforcement integration tests."""

    @pytest.fixture()
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from lip.api.rate_limiter import TokenBucketRateLimiter
        from lip.api.regulatory_router import make_regulatory_router
        from lip.api.regulatory_service import RegulatoryService
        from lip.c8_license_manager.query_metering import RegulatoryQueryMetering
        from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine
        from lip.p10_regulatory_data.telemetry_schema import AnonymizedCorridorResult

        engine = SystemicRiskEngine()
        engine.ingest_results(
            [
                AnonymizedCorridorResult(
                    corridor="EUR-USD",
                    period_label="2029-08-01T14:00Z",
                    total_payments=1000,
                    failed_payments=100,
                    failure_rate=0.10,
                    bank_count=10,
                    k_anonymity_satisfied=True,
                    privacy_budget_remaining=4.5,
                    noise_applied=True,
                    stale=False,
                ),
            ]
        )
        service = RegulatoryService(risk_engine=engine)
        limiter = TokenBucketRateLimiter(rate=1000, period_seconds=3600)
        metering = RegulatoryQueryMetering(metering_key=_KEY)
        app = FastAPI()
        app.include_router(
            make_regulatory_router(
                service,
                rate_limiter=limiter,
                regulator_signing_key=_KEY,
                query_metering=metering,
            ),
            prefix="/api/v1/regulatory",
        )
        return TestClient(app)

    @staticmethod
    def _auth_header(token: RegulatorSubscriptionToken) -> dict[str, str]:
        signed = sign_regulator_token(token, _KEY)
        encoded = encode_regulator_token(signed)
        return {"Authorization": f"Bearer {encoded}"}

    def test_missing_token_returns_401(self, client):
        resp = client.get("/api/v1/regulatory/metadata")
        assert resp.status_code == 401

    def test_valid_token_allows_metadata(self, client):
        token = _make_regulator_token(subscription_tier="STANDARD")
        resp = client.get(
            "/api/v1/regulatory/metadata",
            headers=self._auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["api_version"] == "1.0.0"

    def test_tier_restriction_blocks_stress_endpoint(self, client):
        token = _make_regulator_token(subscription_tier="STANDARD")
        resp = client.get(
            "/api/v1/regulatory/contagion/simulate?shock_corridor=EUR-USD",
            headers=self._auth_header(token),
        )
        assert resp.status_code == 403

    def test_corridor_permission_enforced(self, client):
        token = _make_regulator_token(
            subscription_tier="QUERY",
            permitted_corridors=["EUR-*"],
        )
        good = client.get(
            "/api/v1/regulatory/corridors/EUR-USD/trend",
            headers=self._auth_header(token),
        )
        bad = client.get(
            "/api/v1/regulatory/corridors/GBP-EUR/trend",
            headers=self._auth_header(token),
        )
        assert good.status_code == 200
        assert bad.status_code == 403

    def test_monthly_query_budget_enforced(self, client):
        token = _make_regulator_token(
            subscription_tier="STANDARD",
            query_budget_monthly=1,
            privacy_budget_allocation=5.0,
        )
        headers = self._auth_header(token)
        first = client.get("/api/v1/regulatory/metadata", headers=headers)
        second = client.get("/api/v1/regulatory/metadata", headers=headers)
        assert first.status_code == 200
        assert second.status_code == 429

    def test_privacy_budget_enforced(self, client):
        token = _make_regulator_token(
            subscription_tier="STANDARD",
            query_budget_monthly=10,
            privacy_budget_allocation=0.01,
        )
        resp = client.get(
            "/api/v1/regulatory/metadata",
            headers=self._auth_header(token),
        )
        assert resp.status_code == 429
