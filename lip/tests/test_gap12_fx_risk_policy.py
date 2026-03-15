"""
test_gap12_fx_risk_policy.py — Tests for GAP-12:
FX risk policy gate for cross-currency bridge corridors.
"""
import uuid

import pytest

from lip.c7_execution_agent.agent import ExecutionAgent, ExecutionConfig
from lip.c7_execution_agent.decision_log import DecisionLogger
from lip.c7_execution_agent.degraded_mode import DegradedModeManager
from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.kill_switch import KillSwitch
from lip.common.constants import FX_G10_CURRENCIES, FX_RISK_POLICY_DEFAULT
from lip.common.fx_risk_policy import FXRiskConfig, FXRiskPolicy

_HMAC_KEY = b"test_hmac_key_gap12_fx_risk_policy"


def _make_agent(fx_risk_config=None):
    cfg = ExecutionConfig(require_human_review_above_pd=0.99)
    return ExecutionAgent(
        kill_switch=KillSwitch(),
        decision_logger=DecisionLogger(hmac_key=_HMAC_KEY),
        human_override=HumanOverrideInterface(),
        degraded_mode_manager=DegradedModeManager(),
        config=cfg,
        fx_risk_config=fx_risk_config,
    )


def _make_context(currency: str = "USD") -> dict:
    return {
        "uetr": str(uuid.uuid4()),
        "individual_payment_id": "pid-gap12",
        "sending_bic": "TESTBIC1",
        "failure_probability": 0.9,
        "pd_score": 0.05,
        "fee_bps": 300,
        "loan_amount": "500000.00",
        "original_payment_amount_usd": "500000.00",
        "dispute_class": "NOT_DISPUTE",
        "aml_passed": True,
        "maturity_days": 7,
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# 1–5: FXRiskConfig unit tests
# ---------------------------------------------------------------------------

class TestFXRiskConfig:
    def test_same_currency_only_allows_usd_payment_for_usd_bank(self):
        """SAME_CURRENCY_ONLY: USD payment is supported by a USD-funded bank."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        assert cfg.is_supported("USD") is True

    def test_same_currency_only_rejects_eur_payment_for_usd_bank(self):
        """SAME_CURRENCY_ONLY: EUR payment is NOT supported by a USD-funded bank."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        assert cfg.is_supported("EUR") is False

    def test_bank_native_currency_policy_allows_any_currency(self):
        """BANK_NATIVE_CURRENCY: all currencies are supported (bank handles FX)."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.BANK_NATIVE_CURRENCY, bank_base_currency="USD")
        assert cfg.is_supported("EUR") is True
        assert cfg.is_supported("GBP") is True
        assert cfg.is_supported("JPY") is True

    def test_is_g10_true_for_eur(self):
        """EUR is a G10 currency."""
        cfg = FXRiskConfig()
        assert cfg.is_g10("EUR") is True

    def test_is_g10_false_for_em_currency(self):
        """BRL (Brazilian real) is NOT a G10 currency."""
        cfg = FXRiskConfig()
        assert cfg.is_g10("BRL") is False

    def test_constants_match_config_defaults(self):
        """FX_G10_CURRENCIES constant matches FXRiskConfig default set."""
        cfg = FXRiskConfig()
        assert cfg.g10_currencies == FX_G10_CURRENCIES
        assert FX_RISK_POLICY_DEFAULT == FXRiskPolicy.SAME_CURRENCY_ONLY.value


# ---------------------------------------------------------------------------
# 6–9: C7 ExecutionAgent FX gate behaviour
# ---------------------------------------------------------------------------

class TestC7FXGate:
    def test_c7_returns_currency_not_supported_for_blocked_currency(self):
        """EUR payment to USD-funded bank with SAME_CURRENCY_ONLY → CURRENCY_NOT_SUPPORTED."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        agent = _make_agent(fx_risk_config=cfg)
        result = agent.process_payment(_make_context("EUR"))
        assert result["status"] == "CURRENCY_NOT_SUPPORTED"
        assert result["loan_offer"] is None
        assert result["halt_reason"] == "currency_not_supported"

    def test_c7_allows_payment_when_policy_permits(self):
        """USD payment to USD-funded bank with SAME_CURRENCY_ONLY → OFFER."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        agent = _make_agent(fx_risk_config=cfg)
        result = agent.process_payment(_make_context("USD"))
        assert result["status"] == "OFFER"

    def test_c7_with_no_fx_config_does_not_block(self):
        """Without FX config, any currency is accepted (no gate applied)."""
        agent = _make_agent(fx_risk_config=None)
        result = agent.process_payment(_make_context("EUR"))
        assert result["status"] == "OFFER"

    def test_currency_not_supported_produces_decision_log_entry(self):
        """CURRENCY_NOT_SUPPORTED must write a decision log entry for audit trail."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        agent = _make_agent(fx_risk_config=cfg)
        result = agent.process_payment(_make_context("EUR"))
        assert result["status"] == "CURRENCY_NOT_SUPPORTED"
        entry_id = result["decision_entry_id"]
        assert entry_id is not None
        entry = agent.decision_logger.get(entry_id)
        assert entry.decision_type == "CURRENCY_NOT_SUPPORTED"


# ---------------------------------------------------------------------------
# 10: LoanOffer dict includes loan_currency
# ---------------------------------------------------------------------------

class TestLoanOfferLoanCurrency:
    def test_loan_offer_dict_contains_loan_currency(self):
        """C7 offer dict carries loan_currency from payment context (no FX config)."""
        agent = _make_agent(fx_risk_config=None)
        result = agent.process_payment(_make_context("EUR"))
        assert result["status"] == "OFFER"
        assert result["loan_offer"]["loan_currency"] == "EUR"


# ---------------------------------------------------------------------------
# 11–13: EUR-funded bank scenarios
# ---------------------------------------------------------------------------

class TestEURFundedBank:
    @pytest.fixture
    def eur_bank_agent(self):
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="EUR")
        return _make_agent(fx_risk_config=cfg)

    def test_eur_bank_allows_eur_payments(self, eur_bank_agent):
        """EUR-funded bank with SAME_CURRENCY_ONLY → OFFER for EUR payments."""
        result = eur_bank_agent.process_payment(_make_context("EUR"))
        assert result["status"] == "OFFER"

    def test_eur_bank_rejects_usd_payments_under_same_currency_policy(self, eur_bank_agent):
        """EUR-funded bank with SAME_CURRENCY_ONLY → CURRENCY_NOT_SUPPORTED for USD."""
        result = eur_bank_agent.process_payment(_make_context("USD"))
        assert result["status"] == "CURRENCY_NOT_SUPPORTED"

    def test_bank_native_policy_always_funds_in_base_currency(self):
        """BANK_NATIVE_CURRENCY: any currency is accepted; bank handles FX."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.BANK_NATIVE_CURRENCY, bank_base_currency="USD")
        agent = _make_agent(fx_risk_config=cfg)
        for currency in ("USD", "EUR", "GBP", "JPY"):
            result = agent.process_payment(_make_context(currency))
            assert result["status"] == "OFFER", f"Expected OFFER for {currency}"


# ---------------------------------------------------------------------------
# 14: Pipeline-level blocked outcome (via C7 returning CURRENCY_NOT_SUPPORTED)
# ---------------------------------------------------------------------------

class TestPipelineBlockedOnCurrencyNotSupported:
    def test_c7_currency_not_supported_has_decision_log(self):
        """C7 must produce a decision_entry_id when blocking on currency mismatch."""
        cfg = FXRiskConfig(policy=FXRiskPolicy.SAME_CURRENCY_ONLY, bank_base_currency="USD")
        agent = _make_agent(fx_risk_config=cfg)
        result = agent.process_payment(_make_context("GBP"))
        assert result["status"] == "CURRENCY_NOT_SUPPORTED"
        assert result["decision_entry_id"] is not None
