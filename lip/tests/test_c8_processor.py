"""
test_c8_processor.py — Tests for P3 processor token extension and revenue metering.

QUANT domain: revenue metering tests enforce penny-exact Decimal arithmetic.
CIPHER domain: processor token tests enforce HMAC integrity for new fields.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from lip.c8_license_manager.boot_validator import LicenseBootValidator
from lip.c8_license_manager.license_token import (
    ALL_COMPONENTS,
    LicenseeContext,
    LicenseToken,
    ProcessorLicenseeContext,
    sign_token,
    verify_token,
)
from lip.c8_license_manager.revenue_metering import RevenueMetering

_KEY = b"bpi-test-signing-key-32-bytes!!!"


def _make_processor_token(
    licensee_id: str = "FINASTRA_EU_001",
    days_until_expiry: int = 365,
    max_tps: int = 1000,
    aml_dollar_cap: int = 0,
    aml_count_cap: int = 0,
    sub_licensee_bics: list | None = None,
    annual_minimum_usd: int = 500000,
    performance_premium_pct: float = 0.15,
    platform_take_rate_pct: float = 0.20,
) -> LicenseToken:
    today = date.today()
    expiry = today + timedelta(days=days_until_expiry)
    return LicenseToken(
        licensee_id=licensee_id,
        issue_date=today.isoformat(),
        expiry_date=expiry.isoformat(),
        max_tps=max_tps,
        aml_dollar_cap_usd=aml_dollar_cap,
        aml_count_cap=aml_count_cap,
        licensee_type="PROCESSOR",
        sub_licensee_bics=["COBADEFF", "DEUTDEFF"] if sub_licensee_bics is None else sub_licensee_bics,
        annual_minimum_usd=annual_minimum_usd,
        performance_premium_pct=performance_premium_pct,
        platform_take_rate_pct=platform_take_rate_pct,
        permitted_components=list(ALL_COMPONENTS),
    )


# ── Processor Token Tests (CIPHER) ─────────────────────────────────────────


class TestProcessorToken:

    def test_sign_and_verify_processor_token(self):
        token = _make_processor_token()
        signed = sign_token(token, _KEY)
        assert signed.hmac_signature != ""
        assert verify_token(signed, _KEY)

    def test_processor_fields_in_canonical_payload(self):
        """New fields must be in the HMAC-signed payload."""
        token = _make_processor_token()
        payload = token.canonical_payload()
        import json
        data = json.loads(payload)
        assert data["licensee_type"] == "PROCESSOR"
        assert data["sub_licensee_bics"] == ["COBADEFF", "DEUTDEFF"]
        assert data["annual_minimum_usd"] == 500000
        assert data["performance_premium_pct"] == 0.15
        assert data["platform_take_rate_pct"] == 0.20

    def test_sub_licensee_bics_sorted_in_payload(self):
        """BICs must be sorted in canonical payload for deterministic HMAC."""
        token = _make_processor_token(sub_licensee_bics=["DEUTDEFF", "COBADEFF", "BNPAFRPP"])
        payload = token.canonical_payload()
        import json
        data = json.loads(payload)
        assert data["sub_licensee_bics"] == ["BNPAFRPP", "COBADEFF", "DEUTDEFF"]

    def test_bank_token_backward_compatible(self):
        """Existing BANK tokens with default processor fields still verify."""
        token = LicenseToken(
            licensee_id="TEST_BANK_001",
            issue_date=date.today().isoformat(),
            expiry_date=(date.today() + timedelta(days=365)).isoformat(),
            max_tps=500,
            aml_dollar_cap_usd=1000000,
            aml_count_cap=100,
        )
        signed = sign_token(token, _KEY)
        assert verify_token(signed, _KEY)
        assert signed.licensee_type == "BANK"
        assert signed.sub_licensee_bics == []

    def test_round_trip_dict_preserves_processor_fields(self):
        token = _make_processor_token()
        signed = sign_token(token, _KEY)
        d = signed.to_dict()
        restored = LicenseToken.from_dict(d)
        assert restored.licensee_type == "PROCESSOR"
        assert restored.sub_licensee_bics == ["COBADEFF", "DEUTDEFF"]
        assert restored.annual_minimum_usd == 500000
        assert restored.performance_premium_pct == 0.15
        assert restored.platform_take_rate_pct == 0.20
        assert verify_token(restored, _KEY)

    def test_invalid_licensee_type_raises(self):
        d = _make_processor_token().to_dict()
        d["licensee_type"] = "INVALID"
        with pytest.raises(ValueError, match="licensee_type"):
            LicenseToken.from_dict(d)

    def test_tamper_bics_detected(self):
        """Changing sub_licensee_bics after signing must fail verification."""
        signed = sign_token(_make_processor_token(), _KEY)
        signed.sub_licensee_bics.append("HSBCGB2L")
        assert not verify_token(signed, _KEY)


# ── Processor Boot Validator Tests (CIPHER) ──────────────────────────────────


class TestProcessorBootValidator:

    def _env_for_token(self, token: LicenseToken):
        signed = sign_token(token, _KEY)
        return {
            "LIP_LICENSE_TOKEN_JSON": __import__("json").dumps(signed.to_dict()),
            "LIP_LICENSE_KEY_HEX": _KEY.hex(),
        }

    def test_processor_token_returns_processor_context(self, monkeypatch):
        token = _make_processor_token()
        env = self._env_for_token(token)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        ks = MagicMock()
        ks.activate = MagicMock()
        validator = LicenseBootValidator(ks)
        ctx = validator.validate()

        assert ctx is not None
        assert isinstance(ctx, ProcessorLicenseeContext)
        assert ctx.licensee_type == "PROCESSOR"
        assert ctx.sub_licensee_bics == ["COBADEFF", "DEUTDEFF"]
        assert ctx.annual_minimum_usd == 500000

    def test_processor_empty_bics_engages_kill_switch(self, monkeypatch):
        token = _make_processor_token(sub_licensee_bics=[])
        env = self._env_for_token(token)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        ks = MagicMock()
        validator = LicenseBootValidator(ks)
        ctx = validator.validate()

        assert ctx is None
        ks.activate.assert_called_once()
        assert "no_sub_licensees" in ks.activate.call_args[1]["reason"]

    def test_processor_invalid_bic_format_engages_kill_switch(self, monkeypatch):
        token = _make_processor_token(sub_licensee_bics=["INVALID_BIC_TOO_LONG!!"])
        env = self._env_for_token(token)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        ks = MagicMock()
        validator = LicenseBootValidator(ks)
        ctx = validator.validate()

        assert ctx is None
        ks.activate.assert_called_once()

    def test_processor_take_rate_out_of_bounds_engages_kill_switch(self, monkeypatch):
        token = _make_processor_token(platform_take_rate_pct=0.50)
        env = self._env_for_token(token)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        ks = MagicMock()
        validator = LicenseBootValidator(ks)
        ctx = validator.validate()

        assert ctx is None
        ks.activate.assert_called_once()

    def test_bank_token_returns_licensee_context(self, monkeypatch):
        """BANK tokens still return plain LicenseeContext (not Processor)."""
        token = LicenseToken(
            licensee_id="TEST_BANK_001",
            issue_date=date.today().isoformat(),
            expiry_date=(date.today() + timedelta(days=365)).isoformat(),
            max_tps=500,
            aml_dollar_cap_usd=1000000,
            aml_count_cap=100,
        )
        env = self._env_for_token(token)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        ks = MagicMock()
        validator = LicenseBootValidator(ks)
        ctx = validator.validate()

        assert ctx is not None
        assert isinstance(ctx, LicenseeContext)
        assert not isinstance(ctx, ProcessorLicenseeContext)


# ── Revenue Metering Tests (QUANT — TDD) ────────────────────────────────────


class TestRevenueMeteringQuant:
    """QUANT-controlled: all revenue arithmetic must be penny-exact Decimal."""

    def test_single_transaction_fee_split(self):
        rm = RevenueMetering()
        entry = rm.record_transaction(
            tenant_id="FINASTRA_EU_001",
            uetr="test-uetr-001",
            gross_fee_usd=Decimal("1000.00"),
            platform_take_rate_pct=Decimal("0.20"),
        )
        assert entry.processor_take_usd == Decimal("200.00")
        assert entry.bpi_net_usd == Decimal("800.00")

    def test_fee_split_penny_exact(self):
        """processor_take + bpi_net must == gross_fee exactly (no rounding leak)."""
        rm = RevenueMetering()
        entry = rm.record_transaction(
            tenant_id="FINASTRA_EU_001",
            uetr="test-uetr-002",
            gross_fee_usd=Decimal("1000.00"),
            platform_take_rate_pct=Decimal("0.20"),
        )
        assert entry.processor_take_usd + entry.bpi_net_usd == entry.gross_fee_usd

    def test_fee_split_awkward_rounding(self):
        """Rounding residual absorbed by bpi_net (never by processor)."""
        rm = RevenueMetering()
        entry = rm.record_transaction(
            tenant_id="FINASTRA_EU_001",
            uetr="test-uetr-003",
            gross_fee_usd=Decimal("33.33"),
            platform_take_rate_pct=Decimal("0.20"),
        )
        assert entry.processor_take_usd == Decimal("6.67")
        assert entry.bpi_net_usd == Decimal("26.66")
        assert entry.processor_take_usd + entry.bpi_net_usd == entry.gross_fee_usd

    def test_quarterly_summary_no_premium(self):
        """Below baseline: performance premium = $0."""
        rm = RevenueMetering()
        rm.record_transaction("T1", "u1", Decimal("1000.00"), Decimal("0.20"))
        rm.record_transaction("T1", "u2", Decimal("2000.00"), Decimal("0.20"))

        summary = rm.compute_quarterly_summary(
            tenant_id="T1",
            quarter="2027-Q3",
            annual_minimum_usd=Decimal("500000"),
            performance_premium_pct=Decimal("0.15"),
            performance_baseline_usd=Decimal("1000000"),
        )
        assert summary.transaction_count == 2
        assert summary.gross_fee_usd == Decimal("3000.00")
        assert summary.bpi_net_usd == Decimal("2400.00")
        assert summary.performance_premium_usd == Decimal("0")

    def test_quarterly_summary_with_premium(self):
        """Above baseline: premium = (above_baseline) * premium_pct."""
        rm = RevenueMetering()
        rm.record_transaction("T1", "u1", Decimal("50000.00"), Decimal("0.20"))

        summary = rm.compute_quarterly_summary(
            tenant_id="T1",
            quarter="2027-Q3",
            annual_minimum_usd=Decimal("0"),
            performance_premium_pct=Decimal("0.15"),
            performance_baseline_usd=Decimal("10000"),
        )
        assert summary.performance_premium_usd == Decimal("4500.00")
        assert summary.total_bpi_revenue_usd == summary.bpi_net_usd + summary.performance_premium_usd

    def test_annual_minimum_on_track(self):
        rm = RevenueMetering()
        rm.record_transaction("T1", "u1", Decimal("200000.00"), Decimal("0.20"))
        shortfall = rm.check_annual_minimum_shortfall(
            tenant_id="T1",
            annual_minimum_usd=Decimal("100000"),
            year=2027,
        )
        assert shortfall == Decimal("0")

    def test_annual_minimum_shortfall(self):
        rm = RevenueMetering()
        rm.record_transaction("T1", "u1", Decimal("1000.00"), Decimal("0.20"))
        shortfall = rm.check_annual_minimum_shortfall(
            tenant_id="T1",
            annual_minimum_usd=Decimal("500000"),
            year=2027,
        )
        assert shortfall == Decimal("499200.00")

    def test_performance_premium_only_above_baseline(self):
        """Premium on $200K above baseline, not on total $1.2M."""
        rm = RevenueMetering()
        rm.record_transaction("T1", "u1", Decimal("1500000.00"), Decimal("0.20"))
        summary = rm.compute_quarterly_summary(
            tenant_id="T1",
            quarter="2027-Q3",
            annual_minimum_usd=Decimal("0"),
            performance_premium_pct=Decimal("0.10"),
            performance_baseline_usd=Decimal("1000000"),
        )
        assert summary.performance_premium_usd == Decimal("20000.00")

    def test_zero_transactions_quarterly_summary(self):
        rm = RevenueMetering()
        summary = rm.compute_quarterly_summary(
            tenant_id="T1",
            quarter="2027-Q3",
            annual_minimum_usd=Decimal("500000"),
            performance_premium_pct=Decimal("0.15"),
            performance_baseline_usd=Decimal("1000000"),
        )
        assert summary.transaction_count == 0
        assert summary.gross_fee_usd == Decimal("0")
        assert summary.total_bpi_revenue_usd == Decimal("0")

    def test_decimal_types_not_float(self):
        rm = RevenueMetering()
        entry = rm.record_transaction("T1", "u1", Decimal("1000.00"), Decimal("0.20"))
        assert isinstance(entry.gross_fee_usd, Decimal)
        assert isinstance(entry.processor_take_usd, Decimal)
        assert isinstance(entry.bpi_net_usd, Decimal)
