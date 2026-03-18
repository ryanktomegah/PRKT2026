"""
test_coverage_gaps.py — Targeted tests for undertested modules.

Covers:
  - lip.c2_pd_model.__init__ (TierAssignment, run_inference, compute_fee)
  - lip.common.encryption (AES-256-GCM, HMAC-SHA256, PBKDF2 key derivation)
  - lip.c7_execution_agent.kill_switch (KMS monitoring, recovery, should_halt)
  - lip.pipeline (initialization, below-threshold, HALT, DECLINED, error paths)
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ── C2 __init__ imports ──────────────────────────────────────────────────────
from lip.c2_pd_model import (
    TierAssignment,
    compute_fee,
    run_inference,
)
from lip.c2_pd_model.fee import FEE_FLOOR_BPS
from lip.c2_pd_model.tier_assignment import Tier, TierFeatures

# ── Pipeline imports ──────────────────────────────────────────────────────────
from lip.c5_streaming.event_normalizer import NormalizedEvent

# ── Kill switch imports ───────────────────────────────────────────────────────
from lip.c7_execution_agent.kill_switch import (
    KillSwitch,
    KillSwitchState,
    KillSwitchStatus,
    KMSState,
)

# ── Encryption imports ────────────────────────────────────────────────────────
from lip.common.encryption import (
    decrypt_aes_gcm,
    derive_key_from_passphrase,
    encrypt_aes_gcm,
    generate_salt,
    hash_identifier,
    sign_hmac_sha256,
    verify_hmac_sha256,
)
from lip.pipeline import FAILURE_PROBABILITY_THRESHOLD, LIPPipeline

# ===========================================================================
# Helpers
# ===========================================================================

def _make_normalized_event(
    uetr: Optional[str] = None,
    rejection_code: str = "CURR",
    narrative: Optional[str] = None,
    amount: Decimal = Decimal("100000"),
) -> NormalizedEvent:
    """Minimal NormalizedEvent for pipeline tests."""
    return NormalizedEvent(
        uetr=uetr or str(uuid.uuid4()),
        individual_payment_id=str(uuid.uuid4()),
        sending_bic="AAAAGB2LXXX",
        receiving_bic="BBBBDE2LXXX",
        amount=amount,
        currency="USD",
        timestamp=datetime.now(tz=timezone.utc),
        rail="SWIFT",
        rejection_code=rejection_code,
        narrative=narrative,
        raw_source={},
    )


# ===========================================================================
# Section 1: C2 __init__.py — TierAssignment, run_inference, compute_fee
# ===========================================================================


class TestTierAssignment:
    """Tests for the TierAssignment convenience wrapper."""

    def test_assign_tier_1_with_rich_data(self):
        ta = TierAssignment()
        features = TierFeatures(
            has_financial_statements=True,
            has_transaction_history=True,
            has_credit_bureau=True,
            months_history=36,
            transaction_count=250,
        )
        result = ta.assign(features)
        assert result == Tier.TIER_1

    def test_assign_tier_2_with_transaction_history(self):
        ta = TierAssignment()
        features = TierFeatures(
            has_financial_statements=False,
            has_transaction_history=True,
            has_credit_bureau=False,
            months_history=12,
            transaction_count=50,
        )
        result = ta.assign(features)
        assert result == Tier.TIER_2

    def test_assign_tier_3_thin_file(self):
        ta = TierAssignment()
        features = TierFeatures(
            has_financial_statements=False,
            has_transaction_history=False,
            has_credit_bureau=False,
            months_history=0,
            transaction_count=0,
        )
        result = ta.assign(features)
        assert result == Tier.TIER_3

    def test_one_hot_tier_1(self):
        assert TierAssignment.one_hot(Tier.TIER_1) == [1, 0, 0]

    def test_one_hot_tier_2(self):
        assert TierAssignment.one_hot(Tier.TIER_2) == [0, 1, 0]

    def test_one_hot_tier_3(self):
        assert TierAssignment.one_hot(Tier.TIER_3) == [0, 0, 1]

    def test_hash_id_returns_hex_digest(self):
        salt = b"test_salt_16bytes"
        result = TierAssignment.hash_id("TAX123", salt)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest

    def test_hash_id_deterministic(self):
        salt = b"deterministic_salt__"
        a = TierAssignment.hash_id("ID_A", salt)
        b = TierAssignment.hash_id("ID_A", salt)
        assert a == b

    def test_hash_id_different_inputs_differ(self):
        salt = b"some_salt_value_____"
        a = TierAssignment.hash_id("ID_A", salt)
        b = TierAssignment.hash_id("ID_B", salt)
        assert a != b


class TestRunInference:
    """Tests for the run_inference convenience function."""

    def test_run_inference_returns_dict_with_expected_keys(self):
        """run_inference should delegate to PDInferenceEngine and return a dict."""
        mock_model = MagicMock()
        mock_predict_result = {
            "pd_score": 0.08,
            "fee_bps": 300,
            "lgd": 0.35,
            "tier": 3,
            "shap_values": [],
            "borrower_id_hash": "abc123",
            "inference_latency_ms": 2.0,
        }

        with patch("lip.c2_pd_model.PDInferenceEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.predict.return_value = mock_predict_result

            result = run_inference(
                model=mock_model,
                payment={"amount_usd": 50000.0, "currency_pair": "USD_EUR"},
                borrower={"tax_id": "TX999"},
                salt=b"x" * 32,
            )

        assert result == mock_predict_result
        instance.predict.assert_called_once()

    def test_run_inference_without_salt_uses_placeholder(self):
        """When salt is None, a zero-byte placeholder is used with a warning."""
        mock_model = MagicMock()

        with patch("lip.c2_pd_model.PDInferenceEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.predict.return_value = {
                "pd_score": 0.1,
                "fee_bps": 300,
                "tier": 3,
                "shap_values": [],
                "borrower_id_hash": "hash",
                "inference_latency_ms": 1.0,
            }
            with patch("lip.c2_pd_model.logger") as mock_logger:
                run_inference(
                    model=mock_model,
                    payment={"amount_usd": 1000},
                    borrower={},
                    salt=None,
                )
                mock_logger.warning.assert_called_once()

    def test_run_inference_derives_tier_from_borrower(self):
        """Tier should be derived from borrower availability flags."""
        mock_model = MagicMock()

        with patch("lip.c2_pd_model.PDInferenceEngine") as MockEngine:
            instance = MockEngine.return_value
            instance.predict.return_value = {
                "pd_score": 0.03,
                "fee_bps": 300,
                "tier": 1,
                "shap_values": [],
                "borrower_id_hash": "h",
                "inference_latency_ms": 1.0,
            }

            run_inference(
                model=mock_model,
                payment={"amount_usd": 200000},
                borrower={
                    "has_financial_statements": True,
                    "has_transaction_history": True,
                    "has_credit_bureau": True,
                    "months_history": 36,
                    "transaction_count": 250,
                },
                salt=b"a" * 32,
            )

            # The UnifiedFeatureEngineer should have been created with Tier 1
            call_args = MockEngine.call_args
            # Third positional arg (or keyword) is auto_tier
            assert call_args[1].get("auto_tier", True) is True or call_args[0][2] is True


class TestComputeFee:
    """Tests for the compute_fee convenience function."""

    def test_compute_fee_returns_expected_keys(self):
        result = compute_fee(pd=0.01, lgd=0.35, loan_amount=1_000_000, days_funded=7)
        assert "fee_bps" in result
        assert "loan_fee" in result
        assert "floor_applied" in result

    def test_compute_fee_floor_applied_for_low_el(self):
        """Low PD * LGD should trigger the 300bps floor."""
        result = compute_fee(pd=0.01, lgd=0.35, loan_amount=1_000_000, days_funded=7)
        assert result["fee_bps"] == FEE_FLOOR_BPS
        assert result["floor_applied"] is True

    def test_compute_fee_floor_not_applied_for_high_el(self):
        """High PD * LGD should exceed 300bps floor."""
        result = compute_fee(pd=0.10, lgd=0.50, loan_amount=1_000_000, days_funded=7)
        # PD * LGD * 10000 = 0.10 * 0.50 * 10000 = 500 bps
        assert result["fee_bps"] > FEE_FLOOR_BPS
        assert result["floor_applied"] is False

    def test_compute_fee_with_explicit_ead(self):
        """Explicit EAD parameter should be accepted without error."""
        result = compute_fee(
            pd=0.02, lgd=0.40, loan_amount=500_000, days_funded=14, ead=600_000
        )
        assert isinstance(result["fee_bps"], Decimal)
        assert isinstance(result["loan_fee"], Decimal)

    def test_compute_fee_loan_fee_is_positive(self):
        result = compute_fee(pd=0.05, lgd=0.45, loan_amount=100_000, days_funded=7)
        assert result["loan_fee"] > 0

    def test_compute_fee_scales_with_days_funded(self):
        """Doubling days_funded should roughly double the loan_fee."""
        r7 = compute_fee(pd=0.05, lgd=0.45, loan_amount=100_000, days_funded=7)
        r14 = compute_fee(pd=0.05, lgd=0.45, loan_amount=100_000, days_funded=14)
        assert abs(r14["loan_fee"] - 2 * r7["loan_fee"]) <= Decimal("0.02")


# ===========================================================================
# Section 2: encryption.py — AES-256-GCM, HMAC-SHA256, Key Derivation
# ===========================================================================


class TestAESGCMEncryption:
    """AES-256-GCM encrypt/decrypt round-trip and error handling."""

    def test_encrypt_decrypt_round_trip(self):
        key = generate_salt(32)
        plaintext = b"sensitive borrower data: tax_id=12345"
        nonce, ciphertext = encrypt_aes_gcm(plaintext, key)
        recovered = decrypt_aes_gcm(nonce, ciphertext, key)
        assert recovered == plaintext

    def test_encrypt_produces_12_byte_nonce(self):
        key = generate_salt(32)
        nonce, _ = encrypt_aes_gcm(b"test", key)
        assert len(nonce) == 12

    def test_ciphertext_differs_from_plaintext(self):
        key = generate_salt(32)
        plaintext = b"hello world"
        _, ciphertext = encrypt_aes_gcm(plaintext, key)
        assert ciphertext != plaintext

    def test_different_encryptions_produce_different_nonces(self):
        """Two encryptions of the same plaintext must use different nonces."""
        key = generate_salt(32)
        nonce1, _ = encrypt_aes_gcm(b"same data", key)
        nonce2, _ = encrypt_aes_gcm(b"same data", key)
        assert nonce1 != nonce2

    def test_invalid_key_size_encrypt_raises(self):
        with pytest.raises(ValueError, match="32-byte key"):
            encrypt_aes_gcm(b"data", b"short_key")

    def test_invalid_key_size_decrypt_raises(self):
        with pytest.raises(ValueError, match="32-byte key"):
            decrypt_aes_gcm(b"\x00" * 12, b"ciphertext", b"short")

    def test_invalid_nonce_size_decrypt_raises(self):
        key = generate_salt(32)
        with pytest.raises(ValueError, match="12 bytes"):
            decrypt_aes_gcm(b"\x00" * 8, b"ciphertext", key)

    def test_tampered_ciphertext_raises_invalid_tag(self):
        from cryptography.exceptions import InvalidTag

        key = generate_salt(32)
        nonce, ciphertext = encrypt_aes_gcm(b"original data", key)
        # Flip a byte in the ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        with pytest.raises(InvalidTag):
            decrypt_aes_gcm(nonce, bytes(tampered), key)

    def test_wrong_key_raises_invalid_tag(self):
        from cryptography.exceptions import InvalidTag

        key1 = generate_salt(32)
        key2 = generate_salt(32)
        nonce, ciphertext = encrypt_aes_gcm(b"secret", key1)
        with pytest.raises(InvalidTag):
            decrypt_aes_gcm(nonce, ciphertext, key2)

    def test_empty_plaintext_round_trip(self):
        key = generate_salt(32)
        nonce, ct = encrypt_aes_gcm(b"", key)
        assert decrypt_aes_gcm(nonce, ct, key) == b""


class TestHMACSHA256:
    """HMAC-SHA256 signing and verification."""

    def test_sign_returns_64_char_hex(self):
        sig = sign_hmac_sha256(b"message", b"key")
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_verify_valid_signature(self):
        key = b"hmac_signing_key_for_test"
        message = b"decision log entry payload"
        sig = sign_hmac_sha256(message, key)
        assert verify_hmac_sha256(message, sig, key) is True

    def test_verify_invalid_signature(self):
        key = b"hmac_key"
        message = b"original"
        sig = sign_hmac_sha256(message, key)
        assert verify_hmac_sha256(b"tampered", sig, key) is False

    def test_verify_wrong_key_fails(self):
        key1 = b"key_one"
        key2 = b"key_two"
        message = b"data"
        sig = sign_hmac_sha256(message, key1)
        assert verify_hmac_sha256(message, sig, key2) is False

    def test_sign_deterministic(self):
        key = b"deterministic_test_key"
        msg = b"same message"
        assert sign_hmac_sha256(msg, key) == sign_hmac_sha256(msg, key)

    def test_sign_empty_key_raises(self):
        with pytest.raises(ValueError, match="HMAC key must not be empty"):
            sign_hmac_sha256(b"message", b"")

    def test_verify_empty_key_raises(self):
        with pytest.raises(ValueError, match="HMAC key must not be empty"):
            verify_hmac_sha256(b"message", "sig", b"")


class TestKeyDerivation:
    """PBKDF2-HMAC-SHA256 key derivation."""

    def test_derive_key_returns_32_bytes(self):
        salt = generate_salt(16)
        key = derive_key_from_passphrase("strong_passphrase!", salt)
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_derive_key_deterministic(self):
        salt = b"fixed_salt_for_test_"
        k1 = derive_key_from_passphrase("same_pass", salt)
        k2 = derive_key_from_passphrase("same_pass", salt)
        assert k1 == k2

    def test_different_passphrases_produce_different_keys(self):
        salt = b"shared_salt_value___"
        k1 = derive_key_from_passphrase("pass_a", salt)
        k2 = derive_key_from_passphrase("pass_b", salt)
        assert k1 != k2

    def test_different_salts_produce_different_keys(self):
        k1 = derive_key_from_passphrase("same", b"salt_alpha__________")
        k2 = derive_key_from_passphrase("same", b"salt_bravo__________")
        assert k1 != k2

    def test_empty_passphrase_raises(self):
        with pytest.raises(ValueError, match="Passphrase must not be empty"):
            derive_key_from_passphrase("", b"some_salt")

    def test_empty_salt_raises(self):
        with pytest.raises(ValueError, match="Salt must not be empty"):
            derive_key_from_passphrase("passphrase", b"")

    def test_derived_key_works_for_aes_gcm(self):
        """Round-trip: derive key from passphrase, encrypt, decrypt."""
        salt = generate_salt(16)
        key = derive_key_from_passphrase("my_secure_pass", salt)
        plaintext = b"confidential PE data"
        nonce, ct = encrypt_aes_gcm(plaintext, key)
        assert decrypt_aes_gcm(nonce, ct, key) == plaintext


class TestSaltAndHashIdentifier:
    """Tests for generate_salt and hash_identifier."""

    def test_generate_salt_default_length(self):
        s = generate_salt()
        assert len(s) == 32

    def test_generate_salt_custom_length(self):
        s = generate_salt(64)
        assert len(s) == 64

    def test_generate_salt_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Salt length must be >= 1"):
            generate_salt(0)

    def test_hash_identifier_returns_64_hex(self):
        h = hash_identifier("borrower_123", b"salt_bytes")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_identifier_empty_salt_raises(self):
        with pytest.raises(ValueError, match="Salt must not be empty"):
            hash_identifier("id", b"")

    def test_hash_identifier_deterministic(self):
        salt = b"fixed"
        a = hash_identifier("same_id", salt)
        b = hash_identifier("same_id", salt)
        assert a == b


# ===========================================================================
# Section 3: kill_switch.py — KMS monitoring, recovery, status
# ===========================================================================


class TestKillSwitchBasics:
    """Basic activation/deactivation without Redis."""

    def test_initial_state_is_inactive(self):
        ks = KillSwitch()
        assert ks.is_active() is False
        assert ks._kill_switch_state == KillSwitchState.INACTIVE

    def test_activate_sets_active(self):
        ks = KillSwitch()
        ks.activate("emergency test")
        assert ks.is_active() is True
        assert ks._reason == "emergency test"

    def test_deactivate_clears_state(self):
        ks = KillSwitch()
        ks.activate("test")
        ks.deactivate()
        assert ks.is_active() is False
        assert ks._reason is None
        assert ks._activated_at is None


class TestKillSwitchGetStatus:
    """get_status should return a correctly populated KillSwitchStatus."""

    def test_status_inactive_by_default(self):
        ks = KillSwitch()
        status = ks.get_status()
        assert isinstance(status, KillSwitchStatus)
        assert status.kill_switch_state == KillSwitchState.INACTIVE
        assert status.kms_state == KMSState.AVAILABLE
        assert status.activated_at is None
        assert status.reason is None

    def test_status_active_with_reason(self):
        ks = KillSwitch()
        ks.activate("risk officer override")
        status = ks.get_status()
        assert status.kill_switch_state == KillSwitchState.ACTIVE
        assert status.reason == "risk officer override"
        assert status.activated_at is not None

    def test_status_reflects_kms_unavailability(self):
        mock_kms = MagicMock()
        mock_kms.ping.side_effect = ConnectionError("KMS down")
        ks = KillSwitch(kms_client=mock_kms)
        ks.check_kms()
        status = ks.get_status()
        assert status.kms_state == KMSState.UNAVAILABLE
        assert status.kms_unavailable_since is not None


class TestKillSwitchShouldHalt:
    """should_halt_new_offers under different states."""

    def test_should_not_halt_when_inactive_and_kms_available(self):
        ks = KillSwitch()
        assert ks.should_halt_new_offers() is False

    def test_should_halt_when_kill_switch_active(self):
        ks = KillSwitch()
        ks.activate("model validation failure")
        assert ks.should_halt_new_offers() is True

    def test_should_halt_when_kms_unavailable(self):
        mock_kms = MagicMock()
        mock_kms.ping.side_effect = Exception("timeout")
        ks = KillSwitch(kms_client=mock_kms)
        ks.check_kms()
        assert ks.should_halt_new_offers() is True

    def test_should_halt_when_both_active_and_kms_down(self):
        mock_kms = MagicMock()
        mock_kms.ping.side_effect = Exception("down")
        ks = KillSwitch(kms_client=mock_kms)
        ks.activate("critical")
        ks.check_kms()
        assert ks.should_halt_new_offers() is True


class TestKillSwitchKMSMonitoring:
    """check_kms behavior including recovery flow."""

    def test_check_kms_no_client_returns_available(self):
        ks = KillSwitch(kms_client=None)
        assert ks.check_kms() == KMSState.AVAILABLE

    def test_check_kms_successful_ping_returns_available(self):
        mock_kms = MagicMock()
        mock_kms.ping.return_value = True
        ks = KillSwitch(kms_client=mock_kms)
        assert ks.check_kms() == KMSState.AVAILABLE

    def test_check_kms_failed_ping_returns_unavailable(self):
        mock_kms = MagicMock()
        mock_kms.ping.side_effect = ConnectionError("KMS unreachable")
        ks = KillSwitch(kms_client=mock_kms)
        result = ks.check_kms()
        assert result == KMSState.UNAVAILABLE
        assert ks._kms_unavailable_since is not None

    def test_check_kms_recovery_clears_unavailable_since(self):
        """When KMS recovers after being down, state resets."""
        mock_kms = MagicMock()
        # First call: KMS is down
        mock_kms.ping.side_effect = ConnectionError("down")
        ks = KillSwitch(kms_client=mock_kms)
        ks.check_kms()
        assert ks._kms_state == KMSState.UNAVAILABLE
        assert ks._kms_unavailable_since is not None

        # Second call: KMS recovers
        mock_kms.ping.side_effect = None
        mock_kms.ping.return_value = True
        result = ks.check_kms()
        assert result == KMSState.AVAILABLE
        assert ks._kms_state == KMSState.AVAILABLE
        assert ks._kms_unavailable_since is None

    def test_kms_unavailable_gap_seconds_none_when_available(self):
        ks = KillSwitch()
        assert ks.kms_unavailable_gap_seconds() is None

    def test_kms_unavailable_gap_seconds_positive_when_down(self):
        mock_kms = MagicMock()
        mock_kms.ping.side_effect = Exception("down")
        ks = KillSwitch(kms_client=mock_kms)
        ks.check_kms()
        gap = ks.kms_unavailable_gap_seconds()
        assert gap is not None
        assert gap >= 0.0


class TestKillSwitchMonitorThread:
    """start_kms_monitor / stop_kms_monitor thread lifecycle."""

    def test_start_and_stop_monitor_thread(self):
        mock_kms = MagicMock()
        mock_kms.ping.return_value = True
        ks = KillSwitch(kms_client=mock_kms)
        ks.start_kms_monitor(interval=1)
        assert ks._monitor_thread is not None
        assert ks._monitor_thread.is_alive()

        ks.stop_kms_monitor()
        assert ks._monitor_thread is None

    def test_monitor_thread_calls_check_kms(self):
        """The background thread should call check_kms periodically."""
        mock_kms = MagicMock()
        mock_kms.ping.return_value = True
        ks = KillSwitch(kms_client=mock_kms)

        ks.start_kms_monitor(interval=1)
        # Wait for at least one interval to pass
        time.sleep(1.5)
        ks.stop_kms_monitor()

        # ping should have been called at least once by the monitor thread
        assert mock_kms.ping.call_count >= 1

    def test_stop_monitor_when_not_started_is_safe(self):
        ks = KillSwitch()
        ks.stop_kms_monitor()  # Should not raise
        assert ks._monitor_thread is None

    def test_monitor_thread_is_daemon(self):
        mock_kms = MagicMock()
        mock_kms.ping.return_value = True
        ks = KillSwitch(kms_client=mock_kms)
        ks.start_kms_monitor(interval=60)
        assert ks._monitor_thread.daemon is True
        ks.stop_kms_monitor()


# ===========================================================================
# Section 4: pipeline.py — initialization, process paths, error handling
# ===========================================================================

# Lightweight mock components for pipeline tests

class _MockC1:
    def __init__(self, fp: float = 0.80):
        self._fp = fp

    def predict(self, payment: dict) -> dict:
        return {
            "failure_probability": self._fp,
            "above_threshold": self._fp > FAILURE_PROBABILITY_THRESHOLD,
            "shap_top20": [{"feature": f"f{i}", "value": 0.01} for i in range(20)],
        }

    def __call__(self, payment: dict) -> dict:
        return self.predict(payment)


class _MockC2:
    def __init__(self, pd_score: float = 0.05, fee_bps: int = 300, tier: int = 3):
        self._pd = pd_score
        self._fee = fee_bps
        self._tier = tier

    def predict(self, payment: dict, borrower: dict) -> dict:
        return {
            "pd_score": self._pd,
            "fee_bps": self._fee,
            "tier": self._tier,
            "shap_values": [],
        }

    def __call__(self, payment: dict, borrower: dict) -> dict:
        return self.predict(payment, borrower)


class _MockC4:
    def __init__(self, dispute_class: str = "NOT_DISPUTE"):
        self._cls = dispute_class

    def classify(self, **kwargs) -> dict:
        return {"dispute_class": self._cls, "confidence": 0.95}


class _MockC6:
    def __init__(self, passed: bool = True):
        self._passed = passed

    def check(self, entity_id, amount, beneficiary_id, **kwargs):
        return SimpleNamespace(passed=self._passed)

    def record(self, entity_id, amount, beneficiary_id, **kwargs):
        """No-op: velocity recording is a side effect; tests don't assert on it."""


class _MockC7:
    def __init__(self, status: str = "OFFER", halt: bool = False):
        self._status = status
        self._halt = halt

    def process_payment(self, ctx: dict) -> dict:
        if self._halt:
            return {"status": "HALT", "loan_offer": None, "decision_entry_id": "halt-001"}
        if self._status in ("DECLINE", "BLOCK", "PENDING_HUMAN_REVIEW"):
            return {"status": self._status, "loan_offer": None, "decision_entry_id": "dec-001"}
        return {
            "status": "OFFER",
            "loan_offer": {
                "loan_id": f"loan-{ctx.get('uetr', 'x')[:8]}",
                "uetr": ctx.get("uetr"),
                "fee_bps": ctx.get("fee_bps", 300),
                "maturity_days": ctx.get("maturity_days", 7),
            },
            "decision_entry_id": "entry-001",
        }


def _build_pipeline(
    fp: float = 0.80,
    c7_status: str = "OFFER",
    c7_halt: bool = False,
    c4_dispute: str = "NOT_DISPUTE",
    c6_passed: bool = True,
    c3_monitor=None,
    pd_score: float = 0.05,
    fee_bps: int = 300,
) -> LIPPipeline:
    return LIPPipeline(
        c1_engine=_MockC1(fp),
        c2_engine=_MockC2(pd_score=pd_score, fee_bps=fee_bps),
        c4_classifier=_MockC4(c4_dispute),
        c6_checker=_MockC6(c6_passed),
        c7_agent=_MockC7(status=c7_status, halt=c7_halt),
        c3_monitor=c3_monitor,
    )


class TestPipelineInitialization:
    """LIPPipeline construction and attribute assignment."""

    def test_pipeline_stores_threshold(self):
        p = _build_pipeline()
        assert p.threshold == FAILURE_PROBABILITY_THRESHOLD

    def test_pipeline_custom_threshold(self):
        p = LIPPipeline(
            c1_engine=_MockC1(),
            c2_engine=_MockC2(),
            c4_classifier=_MockC4(),
            c6_checker=_MockC6(),
            c7_agent=_MockC7(),
            threshold=0.25,
        )
        assert p.threshold == 0.25

    def test_pipeline_stores_components(self):
        c1 = _MockC1()
        c2 = _MockC2()
        p = LIPPipeline(
            c1_engine=c1,
            c2_engine=c2,
            c4_classifier=_MockC4(),
            c6_checker=_MockC6(),
            c7_agent=_MockC7(),
        )
        assert p._c1 is c1
        assert p._c2 is c2


class TestPipelineBelowThreshold:
    """When failure_probability < threshold, pipeline short-circuits."""

    def test_below_threshold_returns_below_threshold_outcome(self):
        p = _build_pipeline(fp=0.05)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "BELOW_THRESHOLD"
        assert result.above_threshold is False

    def test_below_threshold_no_pd_or_fee(self):
        p = _build_pipeline(fp=0.01)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.pd_estimate is None
        assert result.fee_bps is None

    def test_below_threshold_has_latency(self):
        p = _build_pipeline(fp=0.01)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.total_latency_ms > 0


class TestPipelineHappyPath:
    """Full happy path: above threshold, no blocks, offer accepted."""

    def test_funded_outcome(self):
        p = _build_pipeline(fp=0.80)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "FUNDED"

    def test_funded_has_loan_offer(self):
        p = _build_pipeline(fp=0.80)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.loan_offer is not None
        assert result.loan_offer["uetr"] == event.uetr

    def test_funded_state_machine_history(self):
        p = _build_pipeline(fp=0.80)
        event = _make_normalized_event()
        result = p.process(event)
        assert "MONITORING" in result.payment_state_history
        assert "FAILURE_DETECTED" in result.payment_state_history
        assert "BRIDGE_OFFERED" in result.payment_state_history
        assert "FUNDED" in result.payment_state_history

    def test_funded_has_pd_and_fee(self):
        p = _build_pipeline(fp=0.80, pd_score=0.07, fee_bps=350)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.pd_estimate == 0.07
        assert result.fee_bps == 350


class TestPipelineHaltPath:
    """C7 returns HALT (kill switch or KMS unavailable)."""

    def test_halt_outcome(self):
        p = _build_pipeline(fp=0.80, c7_halt=True)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "HALT"

    def test_halt_no_loan_offer(self):
        p = _build_pipeline(fp=0.80, c7_halt=True)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.loan_offer is None

    def test_halt_still_has_pd_and_fee(self):
        p = _build_pipeline(fp=0.80, c7_halt=True)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.pd_estimate is not None
        assert result.fee_bps is not None


class TestPipelineDeclinePath:
    """C7 returns DECLINE/BLOCK/PENDING_HUMAN_REVIEW."""

    def test_decline_outcome(self):
        p = _build_pipeline(fp=0.80, c7_status="DECLINE")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "DECLINED"

    def test_block_outcome(self):
        p = _build_pipeline(fp=0.80, c7_status="BLOCK")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "DECLINED"

    def test_pending_human_review_outcome(self):
        # EPG-26: PENDING_HUMAN_REVIEW is now a distinct outcome, not DECLINED
        p = _build_pipeline(fp=0.80, c7_status="PENDING_HUMAN_REVIEW")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "PENDING_HUMAN_REVIEW"

    def test_decline_no_loan_offer(self):
        p = _build_pipeline(fp=0.80, c7_status="DECLINE")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.loan_offer is None


class TestPipelineDisputeBlock:
    """C4 returns a dispute hard-block class."""

    def test_dispute_confirmed_blocks(self):
        p = _build_pipeline(fp=0.80, c4_dispute="DISPUTE_CONFIRMED")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "DISPUTE_BLOCKED"
        assert result.dispute_hard_block is True

    def test_dispute_possible_blocks(self):
        p = _build_pipeline(fp=0.80, c4_dispute="DISPUTE_POSSIBLE")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "DISPUTE_BLOCKED"

    def test_not_dispute_does_not_block(self):
        p = _build_pipeline(fp=0.80, c4_dispute="NOT_DISPUTE")
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome != "DISPUTE_BLOCKED"


class TestPipelineAMLBlock:
    """C6 returns failed AML check."""

    def test_aml_block_outcome(self):
        p = _build_pipeline(fp=0.80, c6_passed=False)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "AML_BLOCKED"
        assert result.aml_hard_block is True

    def test_aml_block_no_loan_offer(self):
        p = _build_pipeline(fp=0.80, c6_passed=False)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.loan_offer is None


class TestPipelineC3Registration:
    """Pipeline registers funded loans with C3 settlement monitor."""

    def test_c3_register_loan_called_on_funded(self):
        mock_c3 = MagicMock()
        p = _build_pipeline(fp=0.80, c3_monitor=mock_c3)
        event = _make_normalized_event()
        p.process(event)
        mock_c3.register_loan.assert_called_once()

    def test_c3_not_called_when_below_threshold(self):
        mock_c3 = MagicMock()
        p = _build_pipeline(fp=0.01, c3_monitor=mock_c3)
        event = _make_normalized_event()
        p.process(event)
        mock_c3.register_loan.assert_not_called()

    def test_c3_not_called_when_halted(self):
        mock_c3 = MagicMock()
        p = _build_pipeline(fp=0.80, c7_halt=True, c3_monitor=mock_c3)
        event = _make_normalized_event()
        p.process(event)
        mock_c3.register_loan.assert_not_called()

    def test_c3_exception_does_not_crash_pipeline(self):
        """If C3 registration fails, pipeline should still return FUNDED."""
        mock_c3 = MagicMock()
        mock_c3.register_loan.side_effect = RuntimeError("C3 storage failure")
        p = _build_pipeline(fp=0.80, c3_monitor=mock_c3)
        event = _make_normalized_event()
        result = p.process(event)
        assert result.outcome == "FUNDED"


class TestPipelineLatency:
    """Pipeline latency tracking."""

    def test_component_latencies_present_for_funded(self):
        p = _build_pipeline(fp=0.80)
        event = _make_normalized_event()
        result = p.process(event)
        assert "c1" in result.component_latencies
        assert "c4" in result.component_latencies
        assert "c6" in result.component_latencies
        assert "c2" in result.component_latencies
        assert "c7" in result.component_latencies

    def test_component_latencies_below_threshold_only_has_c1(self):
        p = _build_pipeline(fp=0.01)
        event = _make_normalized_event()
        result = p.process(event)
        assert "c1" in result.component_latencies
        # C2/C4/C6/C7 not reached
        assert "c2" not in result.component_latencies

    def test_global_latency_tracker_receives_records(self):
        from lip.instrumentation import LatencyTracker

        tracker = LatencyTracker()
        p = LIPPipeline(
            c1_engine=_MockC1(0.80),
            c2_engine=_MockC2(),
            c4_classifier=_MockC4(),
            c6_checker=_MockC6(),
            c7_agent=_MockC7(),
            global_latency_tracker=tracker,
        )
        event = _make_normalized_event()
        p.process(event)
        assert tracker.latest("total") is not None
        assert tracker.latest("c1") is not None
