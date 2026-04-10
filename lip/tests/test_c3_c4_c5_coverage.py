"""
test_c3_c4_c5_coverage.py -- Targeted coverage tests for C3, C4, C5 gaps.

Covers missing lines identified by coverage analysis:
  C3 repayment_loop.py   (lines 130-132,136-138,143-144,177-178,265-266,308-309,344-345,379,408-431,435-442)
  C3 settlement_handlers.py (lines 59,65-72,129-131,161-162)
  C3 uetr_mapping.py      (lines 52-53,69-75,89-90)
  C4 backends.py           (lines 117,149-151,162-166,178-182)
  C4 model.py              (lines 80-81,88,90,92,127-128,214-222,229,241-246,273-283)
  C4 multilingual.py       (lines 251-276)
  C5 kafka_worker.py       (lines 79-87,90-97,102-103,115-149,205,214-215,235-283)

All Kafka/Redis dependencies are mocked via unittest.mock.
"""
import json
import os
import signal
import sys
import time
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure fake confluent_kafka is available (mirrors test_c5_kafka_worker.py)
# ---------------------------------------------------------------------------

def _install_fake_confluent_kafka():
    if "confluent_kafka" in sys.modules and not isinstance(
        sys.modules["confluent_kafka"], types.ModuleType
    ):
        return
    ck = types.ModuleType("confluent_kafka")

    class _FakeMessage:
        def __init__(self, value, key=None, offset=0, error=None):
            self._value = value
            self._key = key
            self._offset = offset
            self._error = error

        def value(self):
            return self._value

        def key(self):
            return self._key

        def offset(self):
            return self._offset

        def error(self):
            return self._error

    class _FakeConsumer:
        def __init__(self, cfg):
            self._subscribed = []
            self._messages = []

        def subscribe(self, topics):
            self._subscribed = topics

        def poll(self, timeout=1.0):
            if self._messages:
                return self._messages.pop(0)
            return None

        def close(self):
            pass

    class _FakeProducer:
        def __init__(self, cfg):
            self.produced = []

        def produce(self, topic, key=None, value=None, headers=None):
            self.produced.append({"topic": topic, "key": key, "value": value, "headers": headers})

        def poll(self, timeout=0):
            pass

        def flush(self, timeout=10):
            pass

    ck.Consumer = _FakeConsumer
    ck.Producer = _FakeProducer
    ck._FakeMessage = _FakeMessage
    sys.modules["confluent_kafka"] = ck
    return ck


_install_fake_confluent_kafka()

# ---------------------------------------------------------------------------
# Imports (after fake confluent_kafka is installed)
# ---------------------------------------------------------------------------

from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer  # noqa: E402
from lip.c3_repayment_engine.repayment_loop import (  # noqa: E402
    ActiveLoan,
    RepaymentLoop,
    RepaymentTrigger,
    SettlementMonitor,
)
from lip.c3_repayment_engine.settlement_handlers import (  # noqa: E402
    FedNowHandler,
    SEPAHandler,
    SettlementHandlerRegistry,
    SettlementRail,
    SWIFTCamt054Handler,
    _parse_datetime,
    _parse_decimal,
)
from lip.c3_repayment_engine.uetr_mapping import UETRMappingTable  # noqa: E402
from lip.c4_dispute_classifier.model import (  # noqa: E402
    DisputeClassifier,
    MockLLMBackend,
)
from lip.c4_dispute_classifier.multilingual import (  # noqa: E402
    MultilingualNarrativeProcessor,
)
from lip.c4_dispute_classifier.taxonomy import DisputeClass  # noqa: E402
from lip.c5_streaming.kafka_config import KafkaConfig  # noqa: E402
from lip.c5_streaming.kafka_worker import PaymentEventWorker  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor():
    registry = SettlementHandlerRegistry.create_default()
    um = UETRMappingTable()
    cb = CorridorBuffer()
    return SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)


def _make_loan(rejection_class="CLASS_B", past_maturity=False, uetr=None, loan_id=None) -> ActiveLoan:
    funded_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    if past_maturity:
        maturity = datetime.now(tz=timezone.utc) - timedelta(seconds=5)
    else:
        maturity = datetime.now(tz=timezone.utc) + timedelta(days=7)
    return ActiveLoan(
        loan_id=loan_id or str(uuid.uuid4()),
        uetr=uetr or str(uuid.uuid4()),
        individual_payment_id=str(uuid.uuid4()),
        principal=Decimal("50000"),
        fee_bps=300,
        maturity_date=maturity,
        rejection_class=rejection_class,
        corridor="USD_EUR",
        funded_at=funded_at,
    )


def _make_swift_payload(uetr="test-uetr-001", rejection_code="AC01"):
    return {
        "GrpHdr": {
            "MsgId": uetr,
            "CreDtTm": "2024-03-01T12:00:00",
            "InstdAgt": {"FinInstnId": {"BIC": "CHASUS33XXX"}},
        },
        "TxInfAndSts": {
            "OrgnlEndToEndId": f"PAY-{uetr}",
            "StsRsnInf": {"Rsn": {"Cd": rejection_code}},
            "OrgnlTxRef": {
                "Amt": {"InstdAmt": {"value": "50000.00", "Ccy": "EUR"}}
            },
            "AddtlInf": "Test payment",
        },
        "DbtrAgt": {"FinInstnId": {"BIC": "DEUTDEDBFRA"}},
        "rail": "SWIFT",
    }


def _make_kafka_message(payload: dict, offset: int = 0):
    import confluent_kafka as ck
    uetr = payload.get("GrpHdr", {}).get("MsgId", payload.get("uetr", ""))
    return ck._FakeMessage(
        value=json.dumps(payload).encode("utf-8"),
        key=uetr.encode("utf-8") if uetr else None,
        offset=offset,
    )


# ===========================================================================
# C3: repayment_loop.py -- missing lines
# ===========================================================================

class TestSettlementMonitorProcessSignalGaps:
    """Cover lines 130-132 (unknown rail), 136-138 (handler dispatch exception),
    143-144 (RTP UETR resolution), 177-178 (get_active_loans)."""

    def test_unknown_rail_returns_none(self):
        """Line 130-132: Unknown settlement rail logged and returns None."""
        monitor = _make_monitor()
        result = monitor.process_signal("PIGEONPOST", {"uetr": "abc"})
        assert result is None

    def test_handler_dispatch_exception_returns_none(self):
        """Line 136-138: If handler.dispatch raises, process_signal returns None."""
        registry = MagicMock()
        registry.dispatch.side_effect = RuntimeError("handler exploded")
        um = UETRMappingTable()
        cb = CorridorBuffer()
        monitor = SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)
        result = monitor.process_signal("SWIFT", {"uetr": "abc"})
        assert result is None

    def test_rtp_uetr_resolution_from_mapping(self):
        """Lines 143-144: RTP signal with empty uetr resolves via mapping table.

        The RTPHandler always falls back to end_to_end_id for the uetr field,
        so we must mock the handler to return an empty uetr to exercise the
        resolution path in SettlementMonitor.process_signal.
        """
        from lip.c3_repayment_engine.settlement_handlers import SettlementSignal

        real_uetr = str(uuid.uuid4())
        e2e_id = "RTP-E2E-9999"

        # Mock registry to return a signal with empty uetr (triggering line 142-143)
        fake_signal = SettlementSignal(
            uetr="",
            individual_payment_id=e2e_id,
            rail=SettlementRail.RTP,
            amount=Decimal("1000.00"),
            currency="USD",
            settlement_time=datetime.now(tz=timezone.utc),
            raw_message={},
            rejection_code=None,
        )
        registry = MagicMock()
        registry.dispatch.return_value = fake_signal

        um = UETRMappingTable()
        um.store(e2e_id, real_uetr, maturity_days=7)

        cb = CorridorBuffer()
        monitor = SettlementMonitor(handler_registry=registry, uetr_mapping=um, corridor_buffer=cb)

        # Register a loan with the real UETR
        loan = _make_loan(uetr=real_uetr)
        monitor.register_loan(loan)

        result = monitor.process_signal("RTP", {})
        assert result is not None
        assert result["uetr"] == real_uetr
        assert result["trigger"] == RepaymentTrigger.SETTLEMENT_CONFIRMED

    def test_get_active_loans_returns_snapshot(self):
        """Lines 177-178: get_active_loans returns list of all registered loans."""
        monitor = _make_monitor()
        loan1 = _make_loan()
        loan2 = _make_loan()
        monitor.register_loan(loan1)
        monitor.register_loan(loan2)

        active = monitor.get_active_loans()
        assert len(active) == 2
        uetrs = {loan.uetr for loan in active}
        assert loan1.uetr in uetrs
        assert loan2.uetr in uetrs


class TestRepaymentLoopRedisExceptionFallback:
    """Cover lines 265-266: Redis SETNX fails, falls back to in-memory."""

    def test_redis_setnx_exception_falls_back_to_memory(self):
        mock_redis = MagicMock()
        mock_redis.set.side_effect = ConnectionError("Redis down")

        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(
            monitor=monitor,
            repayment_callback=lambda r: records.append(r),
            redis_client=mock_redis,
        )
        loan = _make_loan()
        loop.register_loan(loan)

        result = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)
        # Despite Redis failure, repayment proceeds via in-memory fallback
        assert result != {}
        assert len(records) == 1


class TestRepaymentLoopMaturityDaysMapping:
    """Cover lines 308-309: rejection_class mapping to maturity_days in trigger_repayment."""

    def test_class_a_maturity_days_3(self):
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: records.append(r))
        loan = _make_loan(rejection_class="CLASS_A")
        loop.register_loan(loan)
        result = loop.trigger_repayment(loan, RepaymentTrigger.MATURITY_REACHED, loan.principal)
        assert result["rejection_class"] == "CLASS_A"
        assert result != {}

    def test_class_c_maturity_days_21(self):
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: records.append(r))
        loan = _make_loan(rejection_class="CLASS_C")
        loop.register_loan(loan)
        result = loop.trigger_repayment(loan, RepaymentTrigger.MATURITY_REACHED, loan.principal)
        assert result["rejection_class"] == "CLASS_C"
        assert result != {}


class TestRepaymentLoopCallbackException:
    """Cover lines 344-345: Callback raising an exception is caught."""

    def test_callback_exception_does_not_prevent_deregistration(self):
        monitor = _make_monitor()

        def exploding_callback(record):
            raise RuntimeError("callback error!")

        loop = RepaymentLoop(monitor=monitor, repayment_callback=exploding_callback)
        loan = _make_loan()
        loop.register_loan(loan)

        # Should not raise despite callback explosion
        result = loop.trigger_repayment(loan, RepaymentTrigger.SETTLEMENT_CONFIRMED, loan.principal)
        assert result != {}
        # Loan should be deregistered after repayment
        assert monitor.match_loan(loan.uetr) is None


class TestRepaymentLoopNaiveMaturityDateTimezone:
    """Cover line 379: maturity_date without tzinfo gets UTC assigned."""

    def test_naive_maturity_date_treated_as_utc(self):
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: records.append(r))

        # Create loan with naive (tz-unaware) maturity_date in the past
        loan = ActiveLoan(
            loan_id="naive-tz-loan",
            uetr=str(uuid.uuid4()),
            individual_payment_id="pay-001",
            principal=Decimal("10000"),
            fee_bps=300,
            maturity_date=datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(seconds=10),  # naive, past
            rejection_class="CLASS_B",
            corridor="USD_EUR",
            funded_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
        )
        loop.register_loan(loan)
        triggered = loop.check_maturities()
        assert len(triggered) >= 1


class TestRepaymentLoopMonitoringThread:
    """Cover lines 408-431 (run_monitoring_loop) and 435-442 (stop)."""

    def test_run_monitoring_loop_and_stop(self):
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: records.append(r))

        # Start the monitoring loop with a short interval
        loop.run_monitoring_loop(interval_seconds=1)

        # Thread should be alive
        assert loop._thread is not None
        assert loop._thread.is_alive()

        # Calling again should be a no-op (duplicate start)
        loop.run_monitoring_loop(interval_seconds=1)

        # Stop the thread
        loop.stop()
        assert loop._thread is None

    def test_stop_when_no_thread_is_noop(self):
        """Lines 435-436: stop() with no thread started does nothing."""
        monitor = _make_monitor()
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: None)
        # Should not raise
        loop.stop()
        assert loop._thread is None

    def test_monitoring_loop_triggers_matured_loans(self):
        """Lines 419-427: The loop thread calls check_maturities and triggers repayments."""
        monitor = _make_monitor()
        records = []
        loop = RepaymentLoop(monitor=monitor, repayment_callback=lambda r: records.append(r))

        # Register a loan that is already past maturity
        loan = _make_loan(past_maturity=True)
        loop.register_loan(loan)

        loop.run_monitoring_loop(interval_seconds=1)
        # Wait for at least one iteration
        time.sleep(2.5)
        loop.stop()

        # The matured loan should have been triggered
        assert len(records) >= 1


# ===========================================================================
# C3: settlement_handlers.py -- missing lines
# ===========================================================================

class TestSettlementHandlersParsing:
    """Cover lines 59 (_parse_decimal with Decimal), 65-72 (_parse_datetime branches),
    129-131 (SWIFT handler exception path), 161-162 (FedNow TxSts rejection)."""

    def test_parse_decimal_passthrough(self):
        """Line 59: If already a Decimal, return as-is."""
        d = Decimal("123.45")
        assert _parse_decimal(d) is d

    def test_parse_decimal_from_str(self):
        assert _parse_decimal("99.99") == Decimal("99.99")

    def test_parse_decimal_from_int(self):
        assert _parse_decimal(42) == Decimal("42")

    def test_parse_datetime_from_aware_datetime(self):
        """Line 65-68: Aware datetime returned as-is."""
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = _parse_datetime(dt)
        assert result is dt

    def test_parse_datetime_from_naive_datetime(self):
        """Line 66-67: Naive datetime gets UTC attached."""
        dt = datetime(2024, 6, 15, 12, 0, 0)
        result = _parse_datetime(dt)
        assert result.tzinfo is not None

    def test_parse_datetime_from_iso_string(self):
        """Lines 69-72: String parsed and UTC attached if naive."""
        result = _parse_datetime("2024-06-15T12:00:00")
        assert result.year == 2024
        assert result.tzinfo is not None

    def test_swift_handler_exception_raises_value_error(self):
        """Lines 129-131: Malformed camt.054 raises ValueError."""
        handler = SWIFTCamt054Handler()
        # A payload that will cause attribute errors during deep dict traversal
        with pytest.raises(ValueError, match="Invalid camt.054"):
            handler.handle({"BkToCstmrDbtCdtNtfctn": "not_a_dict"})

    def test_fednow_dict_txsts_rejection_code(self):
        """Lines 161-162: FedNow with dict TxSts extracts nested rejection code."""
        handler = FedNowHandler()
        msg = {
            "uetr": "fed-uetr-001",
            "amount": "5000",
            "currency": "USD",
            "TxSts": {
                "RsnInf": {
                    "Rsn": {"Cd": "AC04"}
                }
            },
        }
        sig = handler.handle(msg)
        assert sig.rejection_code == "AC04"


class TestSEPAHandlerRejectionDict:
    """Cover SEPA handler dict-based TxInf rejection code extraction."""

    def test_sepa_txinf_dict_rejection_code(self):
        handler = SEPAHandler()
        msg = {
            "uetr": "sepa-uetr-001",
            "TxInf": {
                "IntrBkSttlmAmt": {"#text": "2000.00", "@Ccy": "EUR"},
                "StsRsnInf": {"Rsn": {"Cd": "FF01"}},
            },
        }
        sig = handler.handle(msg)
        assert sig.rejection_code == "FF01"
        assert sig.currency == "EUR"


class TestRegistryDispatchUnregistered:
    """Cover SettlementHandlerRegistry.dispatch KeyError path."""

    def test_dispatch_unregistered_rail_raises_key_error(self):
        registry = SettlementHandlerRegistry()
        with pytest.raises(KeyError, match="No handler registered"):
            registry.dispatch(SettlementRail.SWIFT, {})


# ===========================================================================
# C3: uetr_mapping.py -- missing lines (Redis paths)
# ===========================================================================

class TestUETRMappingRedis:
    """Cover lines 52-53 (Redis store), 69-75 (Redis lookup), 89-90 (Redis delete)."""

    def test_store_with_redis(self):
        """Lines 52-53: store() calls redis.setex with correct TTL."""
        mock_redis = MagicMock()
        table = UETRMappingTable(redis_client=mock_redis)
        table.store("e2e-001", "uetr-abc", maturity_days=7)
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][2] == "uetr-abc"  # value
        expected_ttl = (7 + 45) * 86_400
        assert call_args[0][1] == expected_ttl  # TTL seconds

    def test_lookup_with_redis_hit(self):
        """Lines 69-75: Redis lookup returns decoded UETR on cache hit."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"uetr-xyz"
        table = UETRMappingTable(redis_client=mock_redis)
        result = table.lookup("e2e-002")
        assert result == "uetr-xyz"

    def test_lookup_with_redis_hit_str(self):
        """Line 73: Redis returns str (not bytes) -- handled gracefully."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "uetr-str"
        table = UETRMappingTable(redis_client=mock_redis)
        result = table.lookup("e2e-003")
        assert result == "uetr-str"

    def test_lookup_with_redis_miss(self):
        """Lines 70-72: Redis lookup returns None on cache miss."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        table = UETRMappingTable(redis_client=mock_redis)
        result = table.lookup("e2e-999")
        assert result is None

    def test_delete_with_redis(self):
        """Lines 89-90: delete() calls redis.delete."""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        table = UETRMappingTable(redis_client=mock_redis)
        table.delete("e2e-del")
        mock_redis.delete.assert_called_once()


# ===========================================================================
# C4: backends.py -- missing lines
# ===========================================================================

class TestOpenAIBackendNonTimeoutException:
    """Cover line 117: Non-timeout exception re-raised from generate()."""

    def test_non_timeout_exception_propagates(self):
        from lip.c4_dispute_classifier.backends import OpenAICompatibleBackend

        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = MagicMock(return_value=MagicMock())
        with patch.dict(sys.modules, {"openai": fake_openai}):
            backend = OpenAICompatibleBackend("https://x.com", "key", "model")

        # Simulate a non-timeout error (e.g. AuthenticationError)
        class AuthenticationError(Exception):
            pass

        backend._client.chat.completions.create.side_effect = AuthenticationError("bad key")
        with pytest.raises(AuthenticationError):
            backend.generate("sys", "user")


class TestBackendFactoryImportErrors:
    """Cover lines 149-151 (github_models ImportError), 162-166 (groq ImportError),
    178-182 (openai_compat ImportError)."""

    def test_github_models_import_error_falls_back_to_mock(self):
        from lip.c4_dispute_classifier.backends import create_backend

        # Force OpenAICompatibleBackend __init__ to raise ImportError
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}):
            with patch(
                "lip.c4_dispute_classifier.backends.OpenAICompatibleBackend",
                side_effect=ImportError("no openai"),
            ):
                backend = create_backend("github_models")
        assert isinstance(backend, MockLLMBackend)

    def test_groq_import_error_falls_back_to_mock(self):
        from lip.c4_dispute_classifier.backends import create_backend

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
            with patch(
                "lip.c4_dispute_classifier.backends.OpenAICompatibleBackend",
                side_effect=ImportError("no openai"),
            ):
                backend = create_backend("groq")
        assert isinstance(backend, MockLLMBackend)

    def test_openai_compat_import_error_falls_back_to_mock(self):
        from lip.c4_dispute_classifier.backends import create_backend

        with patch.dict(
            os.environ,
            {"LIP_C4_BASE_URL": "https://x.com", "LIP_C4_API_KEY": "key", "LIP_C4_MODEL": "m"},
        ):
            with patch(
                "lip.c4_dispute_classifier.backends.OpenAICompatibleBackend",
                side_effect=ImportError("no openai"),
            ):
                backend = create_backend("openai_compat")
        assert isinstance(backend, MockLLMBackend)

    def test_groq_no_key_falls_back(self):
        """Lines 162-163: groq with missing GROQ_API_KEY returns Mock."""
        from lip.c4_dispute_classifier.backends import create_backend

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GROQ_API_KEY", None)
            backend = create_backend("groq")
        assert isinstance(backend, MockLLMBackend)


# ===========================================================================
# C4: model.py -- missing lines
# ===========================================================================

class TestMockLLMBackendBranches:
    """Cover lines 80-81 (simulate_timeout), 88 (DISPUTE_CONFIRMED),
    90 (NEGOTIATION), 92 (DISPUTE_POSSIBLE)."""

    def test_simulate_timeout_raises(self):
        """Lines 80-81: MockLLMBackend with simulate_timeout=True raises TimeoutError."""
        backend = MockLLMBackend(simulate_timeout=True)
        with pytest.raises(TimeoutError, match="simulated timeout"):
            backend.generate("sys", "user", timeout=0.05)

    def test_fraud_returns_dispute_confirmed(self):
        """Line 88: 'fraud' keyword returns DISPUTE_CONFIRMED."""
        backend = MockLLMBackend()
        assert backend.generate("sys", "fraud detected") == "DISPUTE_CONFIRMED"

    def test_unauthorized_returns_dispute_confirmed(self):
        backend = MockLLMBackend()
        assert backend.generate("sys", "unauthorized transaction") == "DISPUTE_CONFIRMED"

    def test_unauthorised_returns_dispute_confirmed(self):
        backend = MockLLMBackend()
        assert backend.generate("sys", "unauthorised charge") == "DISPUTE_CONFIRMED"

    def test_negotiate_returns_negotiation(self):
        """Line 90: 'negotiate' keyword returns NEGOTIATION."""
        backend = MockLLMBackend()
        assert backend.generate("sys", "let us negotiate") == "NEGOTIATION"

    def test_settlement_returns_negotiation(self):
        backend = MockLLMBackend()
        assert backend.generate("sys", "propose a settlement") == "NEGOTIATION"

    def test_dispute_returns_dispute_possible(self):
        """Line 92: 'dispute' keyword returns DISPUTE_POSSIBLE."""
        backend = MockLLMBackend()
        assert backend.generate("sys", "payment dispute filed") == "DISPUTE_POSSIBLE"

    def test_normal_returns_not_dispute(self):
        backend = MockLLMBackend()
        assert backend.generate("sys", "normal payment processing") == "NOT_DISPUTE"


class TestDisputeClassifierEnvBackend:
    """Cover lines 127-128: DisputeClassifier reads LIP_C4_BACKEND env var."""

    def test_env_backend_non_mock_calls_create_backend(self):
        """Lines 127-128: Non-mock env triggers create_backend()."""
        with patch.dict(os.environ, {"LIP_C4_BACKEND": "github_models"}):
            with patch(
                "lip.c4_dispute_classifier.backends.create_backend",
                return_value=MockLLMBackend(),
            ) as mock_create:
                # Need to construct without injecting a backend
                DisputeClassifier(llm_backend=None)
                mock_create.assert_called_once()


class TestDisputeClassifierLLMPaths:
    """Cover lines 214-222 (TimeoutError path), 229 (timeout/None fallback),
    241-246 (invalid token fallback)."""

    def test_timeout_returns_dispute_possible(self):
        """Lines 214-222: LLM TimeoutError -> DISPUTE_POSSIBLE with timeout_occurred=True."""
        timeout_backend = MockLLMBackend(simulate_timeout=True)
        clf = DisputeClassifier(llm_backend=timeout_backend, timeout_seconds=0.05)
        result = clf.classify(rejection_code="AC01", narrative="normal payment")
        assert result["dispute_class"] == DisputeClass.DISPUTE_POSSIBLE
        assert result["timeout_occurred"] is True
        assert result["confidence"] == 0.5

    def test_generic_exception_returns_dispute_possible(self):
        """Lines 220-224: Generic LLM exception -> DISPUTE_POSSIBLE."""
        failing_backend = MagicMock()
        failing_backend.generate.side_effect = RuntimeError("LLM exploded")
        clf = DisputeClassifier(llm_backend=failing_backend)
        result = clf.classify(rejection_code="AC01", narrative="normal payment")
        assert result["dispute_class"] == DisputeClass.DISPUTE_POSSIBLE
        assert result["timeout_occurred"] is True

    def test_invalid_token_falls_back_to_dispute_possible(self):
        """Lines 241-246: LLM returns invalid token -> DISPUTE_POSSIBLE with 0.5 confidence."""
        bad_backend = MagicMock()
        bad_backend.generate.return_value = "INVALID_GARBAGE_TOKEN"
        clf = DisputeClassifier(llm_backend=bad_backend)
        result = clf.classify(rejection_code="AC01", narrative="normal payment")
        assert result["dispute_class"] == DisputeClass.DISPUTE_POSSIBLE
        assert result["confidence"] == 0.5
        assert result["timeout_occurred"] is False


class TestDisputeClassifierBatch:
    """Cover lines 273-283: classify_batch processes list of cases."""

    def test_classify_batch_returns_list(self):
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        cases = [
            {"rejection_code": "DISP", "narrative": "disputed"},
            {"rejection_code": "AC01", "narrative": "normal payment"},
            {"rejection_code": None, "narrative": "fraud detected"},
        ]
        results = clf.classify_batch(cases)
        assert len(results) == 3
        assert all("dispute_class" in r for r in results)

    def test_classify_batch_empty_list(self):
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        results = clf.classify_batch([])
        assert results == []

    def test_classify_batch_optional_fields(self):
        """Batch cases with amount, currency, counterparty."""
        clf = DisputeClassifier(llm_backend=MockLLMBackend())
        cases = [
            {
                "rejection_code": "AC01",
                "narrative": "insufficient funds",
                "amount": "5000.00",
                "currency": "EUR",
                "counterparty": "DEUTDEFF",
            },
        ]
        results = clf.classify_batch(cases)
        assert len(results) == 1


# ===========================================================================
# C4: multilingual.py -- missing lines (251-276: extract_dispute_keywords)
# ===========================================================================

class TestMultilingualExtractDisputeKeywords:
    """Cover lines 251-276: extract_dispute_keywords for EN + DE/FR/ES banks."""

    def test_english_confirmed_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("this is a fraud dispute", "EN")
        assert "fraud" in found
        assert "dispute" in found

    def test_english_negotiation_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("we want to negotiate a settlement", "EN")
        assert "negotiate" in found
        assert "settlement" in found

    def test_german_confirmed_keywords(self):
        """Language-specific DE confirmed keywords."""
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("betrug streitig nicht genehmigt", "DE")
        assert "betrug" in found
        assert "streitig" in found
        assert "nicht genehmigt" in found

    def test_german_negotiation_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("verhandlung einigung", "DE")
        assert "verhandlung" in found
        assert "einigung" in found

    def test_french_confirmed_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("fraude contestation litige", "FR")
        assert "fraude" in found
        assert "contestation" in found
        assert "litige" in found

    def test_french_negotiation_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("paiement partiel offre acceptée", "FR")
        assert "paiement partiel" in found

    def test_spanish_confirmed_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("fraude disputado no autorizado", "ES")
        assert "fraude" in found
        assert "disputado" in found
        assert "no autorizado" in found

    def test_spanish_negotiation_keywords(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("pago parcial acuerdo parcial", "ES")
        assert "pago parcial" in found

    def test_unsupported_language_returns_english_only(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("this is a fraud case", "ZH")
        # Only English baseline keywords should match
        assert "fraud" in found

    def test_no_keywords_found(self):
        processor = MultilingualNarrativeProcessor()
        found = processor.extract_dispute_keywords("normal payment completed", "EN")
        assert found == []


# ===========================================================================
# C5: kafka_worker.py -- missing lines
# ===========================================================================

class TestPaymentEventWorkerBuildConsumerProducer:
    """Cover lines 79-87 (_build_consumer), 90-97 (_build_producer)."""

    def test_build_consumer_creates_confluent_consumer(self):
        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=True)
        consumer = worker._build_consumer()
        # Should be an instance of our fake Consumer
        import confluent_kafka as ck
        assert isinstance(consumer, ck.Consumer)

    def test_build_producer_creates_confluent_producer(self):
        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=False)
        producer = worker._build_producer()
        import confluent_kafka as ck
        assert isinstance(producer, ck.Producer)


class TestPaymentEventWorkerSignalHandling:
    """Cover lines 102-103 (_handle_signal)."""

    def test_handle_signal_sets_running_false(self):
        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=True)
        worker._running = True
        worker._handle_signal(signal.SIGTERM, None)
        assert worker._running is False


class TestPaymentEventWorkerRunLoop:
    """Cover lines 115-149: run() consumer loop with subscribe, poll, shutdown."""

    def test_run_processes_messages_and_stops(self):
        """Simulate run() with a consumer that returns one message then triggers stop."""
        import confluent_kafka as ck

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        received = []

        def pipeline(event):
            received.append(event.uetr)
            return {"uetr": event.uetr, "status": "ok"}

        worker = PaymentEventWorker(cfg, pipeline, dry_run=True)

        # Build a fake consumer that returns one msg, then None + sets _running=False
        payload = _make_swift_payload(uetr="run-loop-001")
        msg = _make_kafka_message(payload)

        call_count = [0]
        fake_consumer = ck.Consumer({})
        fake_consumer._messages = [msg]

        def limited_poll(self_c, timeout=1.0):
            call_count[0] += 1
            if fake_consumer._messages:
                return fake_consumer._messages.pop(0)
            worker._running = False
            return None

        # Patch _build_consumer and _build_producer
        worker._build_consumer = lambda: fake_consumer
        worker._build_producer = lambda: None

        # Monkey-patch poll on the fake consumer
        fake_consumer.poll = lambda timeout=1.0: limited_poll(fake_consumer, timeout)

        # Override signal.signal to avoid interfering with test runner
        with patch("signal.signal"):
            worker.run(topic_override="test-topic")

        assert "run-loop-001" in received
        assert worker._processed >= 1


class TestPaymentEventWorkerDeadLetterDryRun:
    """Cover line 205: _route_dead_letter with dry_run skips produce."""

    def test_dead_letter_dry_run_noop(self):
        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=True)
        worker._producer = None
        # Should not raise
        mock_msg = MagicMock()
        worker._route_dead_letter(mock_msg)

    def test_dead_letter_producer_exception_logged(self):
        """Lines 214-215: Exception in dead letter produce is logged, not raised."""
        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=False)

        failing_producer = MagicMock()
        failing_producer.produce.side_effect = RuntimeError("produce failed")
        worker._producer = failing_producer

        mock_msg = MagicMock()
        mock_msg.key.return_value = b"key"
        mock_msg.value.return_value = b"val"

        # Should not raise
        worker._route_dead_letter(mock_msg)


class TestPaymentEventWorkerConsumerErrorMsg:
    """Cover lines 137-139: consumer receives a message with an error."""

    def test_message_with_error_is_skipped(self):
        import confluent_kafka as ck

        cfg = KafkaConfig(bootstrap_servers=["localhost:9092"])
        worker = PaymentEventWorker(cfg, lambda e: {}, dry_run=True)

        # Fake consumer returns error message, then None -> stop
        error_msg = ck._FakeMessage(value=b"irrelevant", error="KafkaError: broker down")

        fake_consumer = ck.Consumer({})
        call_count = [0]

        def limited_poll(timeout=1.0):
            call_count[0] += 1
            if call_count[0] == 1:
                return error_msg
            worker._running = False
            return None

        fake_consumer.poll = limited_poll
        worker._build_consumer = lambda: fake_consumer
        worker._build_producer = lambda: None

        with patch("signal.signal"):
            worker.run(topic_override="test-topic")

        # Error message was skipped, no processing
        assert worker._processed == 0
        assert worker._errors == 0
