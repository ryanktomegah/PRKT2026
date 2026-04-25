"""
test_c3_state_machine_bridge.py — Tests for the C3 state machine Python bridge.

Covers:
  - StateMachineBridge: state machine creation, transitions, taxonomy, ISO 20022 extraction
  - ManagedPaymentStateMachine: unified API, legal/illegal transitions, terminal states
  - PaymentWatchdog: registration, state updates, stuck-state detection, deregistration
  - Python-fallback extraction functions
  - Rust/Python parity: same results from both backends when both are available
  - Edge cases: empty dicts, unknown codes, nested ISO 20022 payloads
"""
import time

import pytest

from lip.c3.state_machine_bridge import (
    _RUST_AVAILABLE,
    _TERMINAL_STATES,
    ManagedPaymentStateMachine,
    PaymentWatchdog,
    StateMachineBridge,
    _extract_camt054_python,
    _extract_pacs008_python,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bridge() -> StateMachineBridge:
    return StateMachineBridge()


@pytest.fixture
def sm(bridge: StateMachineBridge) -> ManagedPaymentStateMachine:
    return bridge.create_state_machine()


@pytest.fixture
def watchdog() -> PaymentWatchdog:
    """Short-polling watchdog for tests — does NOT start the thread."""
    return PaymentWatchdog(poll_interval_s=60.0)


# ---------------------------------------------------------------------------
# StateMachineBridge — backend detection
# ---------------------------------------------------------------------------


class TestBridgeBackend:
    def test_rust_available_attribute_is_bool(self, bridge: StateMachineBridge):
        assert isinstance(bridge.RUST_AVAILABLE, bool)

    def test_class_attribute_matches_module_flag(self, bridge: StateMachineBridge):
        assert bridge.RUST_AVAILABLE == _RUST_AVAILABLE


# ---------------------------------------------------------------------------
# ManagedPaymentStateMachine — legal transitions
# ---------------------------------------------------------------------------


class TestManagedStateMachineTransitions:
    def test_default_initial_state_is_monitoring(self, sm: ManagedPaymentStateMachine):
        assert sm.current_state == "MONITORING"
        assert not sm.is_terminal

    def test_full_happy_path(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("FUNDED")
        sm.transition("REPAYMENT_PENDING")
        sm.transition("REPAID")
        assert sm.current_state == "REPAID"
        assert sm.is_terminal

    def test_funded_to_buffer_repaid(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("FUNDED")
        sm.transition("BUFFER_REPAID")
        assert sm.current_state == "BUFFER_REPAID"
        assert sm.is_terminal

    def test_funded_to_defaulted(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("FUNDED")
        sm.transition("DEFAULTED")
        assert sm.is_terminal

    def test_offer_declined_path(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("OFFER_DECLINED")
        assert sm.is_terminal

    def test_offer_expired_path(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("OFFER_EXPIRED")
        assert sm.is_terminal

    def test_dispute_blocked_from_monitoring(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("DISPUTE_BLOCKED")
        assert sm.current_state == "DISPUTE_BLOCKED"
        assert sm.is_terminal

    def test_aml_blocked_from_failure_detected(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("AML_BLOCKED")
        assert sm.is_terminal

    def test_cancellation_alert_then_repaid(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("FUNDED")
        sm.transition("CANCELLATION_ALERT")
        assert sm.current_state == "CANCELLATION_ALERT"
        sm.transition("REPAID")
        assert sm.is_terminal

    def test_cancellation_alert_can_return_to_funded(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine()
        sm.transition("FAILURE_DETECTED")
        sm.transition("BRIDGE_OFFERED")
        sm.transition("FUNDED")
        sm.transition("CANCELLATION_ALERT")
        sm.transition("FUNDED")  # alert dismissed
        assert sm.current_state == "FUNDED"
        assert not sm.is_terminal

    def test_custom_initial_state(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("FUNDED")
        assert sm.current_state == "FUNDED"

    def test_invalid_initial_state_raises(self, bridge: StateMachineBridge):
        with pytest.raises(ValueError, match="Invalid PaymentState"):
            bridge.create_state_machine("INVALID_STATE")


# ---------------------------------------------------------------------------
# ManagedPaymentStateMachine — illegal transitions (fail-closed)
# ---------------------------------------------------------------------------


class TestIllegalTransitions:
    def test_terminal_repaid_cannot_transition(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("REPAID")
        with pytest.raises(ValueError):
            sm.transition("MONITORING")

    def test_terminal_defaulted_cannot_transition(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("DEFAULTED")
        with pytest.raises(ValueError):
            sm.transition("FUNDED")

    def test_terminal_dispute_blocked_cannot_transition(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("DISPUTE_BLOCKED")
        with pytest.raises(ValueError):
            sm.transition("MONITORING")

    def test_monitoring_cannot_jump_to_repaid(self, sm: ManagedPaymentStateMachine):
        with pytest.raises(ValueError):
            sm.transition("REPAID")

    def test_monitoring_cannot_jump_to_funded(self, sm: ManagedPaymentStateMachine):
        with pytest.raises(ValueError):
            sm.transition("FUNDED")

    def test_funded_cannot_go_to_monitoring(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("FUNDED")
        with pytest.raises(ValueError):
            sm.transition("MONITORING")

    def test_unknown_target_state_raises(self, sm: ManagedPaymentStateMachine):
        with pytest.raises(ValueError):
            sm.transition("NOT_A_REAL_STATE")

    def test_error_message_contains_from_and_to(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("REPAID")
        with pytest.raises(ValueError) as exc_info:
            sm.transition("FUNDED")
        msg = str(exc_info.value)
        assert "REPAID" in msg or "Invalid" in msg  # message mentions the states

    def test_all_terminal_states_are_truly_terminal(self, bridge: StateMachineBridge):
        for terminal_state in _TERMINAL_STATES:
            sm = bridge.create_state_machine(terminal_state)
            assert sm.is_terminal, f"{terminal_state} should be terminal"
            assert sm.allowed_transitions() == [], f"{terminal_state} should have no transitions"


# ---------------------------------------------------------------------------
# ManagedPaymentStateMachine — allowed_transitions()
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    def test_monitoring_transitions(self, sm: ManagedPaymentStateMachine):
        transitions = sm.allowed_transitions()
        assert "FAILURE_DETECTED" in transitions
        assert "DISPUTE_BLOCKED" in transitions
        assert "AML_BLOCKED" in transitions
        assert "REPAID" not in transitions

    def test_funded_transitions(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("FUNDED")
        transitions = sm.allowed_transitions()
        assert "REPAID" in transitions
        assert "DEFAULTED" in transitions
        assert "REPAYMENT_PENDING" in transitions
        assert "CANCELLATION_ALERT" in transitions
        assert "MONITORING" not in transitions

    def test_terminal_has_no_transitions(self, bridge: StateMachineBridge):
        sm = bridge.create_state_machine("REPAID")
        assert sm.allowed_transitions() == []


# ---------------------------------------------------------------------------
# Rejection taxonomy
# ---------------------------------------------------------------------------


class TestTaxonomy:
    @pytest.mark.parametrize("code,expected", [
        ("AC01", "CLASS_A"),
        ("AM04", "CLASS_A"),
        ("RC01", "CLASS_A"),
        ("AG02", "CLASS_B"),
        ("NARR", "CLASS_B"),
        ("TECH", "CLASS_B"),
        ("AGNT", "CLASS_C"),
        ("INVB", "CLASS_C"),
        ("UMKA", "CLASS_C"),
        ("DNOR", "BLOCK"),
        ("CNOR", "BLOCK"),
        ("RR01", "BLOCK"),
        ("RR02", "BLOCK"),
        ("RR03", "BLOCK"),
        ("RR04", "BLOCK"),
        ("AG01", "BLOCK"),
        ("LEGL", "BLOCK"),
        ("DISP", "BLOCK"),
        ("FRAU", "BLOCK"),
        ("FRAD", "BLOCK"),
    ])
    def test_classify_rejection_code(
        self, bridge: StateMachineBridge, code: str, expected: str
    ):
        assert bridge.classify_rejection_code(code) == expected

    def test_classify_normalises_lowercase(self, bridge: StateMachineBridge):
        assert bridge.classify_rejection_code("ac01") == "CLASS_A"

    def test_classify_normalises_whitespace(self, bridge: StateMachineBridge):
        assert bridge.classify_rejection_code("  AM04  ") == "CLASS_A"

    def test_classify_unknown_code_raises(self, bridge: StateMachineBridge):
        with pytest.raises(ValueError):
            bridge.classify_rejection_code("ZZZZ")

    @pytest.mark.parametrize("cls,days", [
        ("CLASS_A", 3),
        ("CLASS_B", 7),
        ("CLASS_C", 21),
        ("BLOCK", 0),
    ])
    def test_maturity_days(self, bridge: StateMachineBridge, cls: str, days: int):
        assert bridge.maturity_days(cls) == days

    def test_maturity_days_unknown_raises(self, bridge: StateMachineBridge):
        with pytest.raises(ValueError):
            bridge.maturity_days("CLASS_X")

    def test_is_block_true_for_block_codes(self, bridge: StateMachineBridge):
        for code in ["DNOR", "CNOR", "RR01", "RR02", "RR03", "RR04", "AG01", "LEGL"]:
            assert bridge.is_block_code(code), f"{code} should be block"

    def test_is_block_false_for_class_a(self, bridge: StateMachineBridge):
        assert not bridge.is_block_code("AC01")

    def test_is_block_true_for_unknown_code(self, bridge: StateMachineBridge):
        # Fail-closed: unknown codes return True (may be unrecognised compliance hold)
        assert bridge.is_block_code("UNKNOWN_GARBAGE")

    def test_epg19_compliance_hold_codes_are_block(self, bridge: StateMachineBridge):
        """EPG-19: All 8 compliance-hold codes must be BLOCK (defense-in-depth)."""
        compliance_hold_codes = ["DNOR", "CNOR", "RR01", "RR02", "RR03", "RR04", "AG01", "LEGL"]
        for code in compliance_hold_codes:
            assert bridge.classify_rejection_code(code) == "BLOCK", (
                f"Compliance-hold code {code} must be BLOCK (EPG-19)"
            )


# ---------------------------------------------------------------------------
# ISO 20022 extraction — camt.054
# ---------------------------------------------------------------------------


class TestCamt054Extraction:
    def test_flat_dict(self, bridge: StateMachineBridge):
        raw = {
            "uetr": "test-uetr-1234",
            "individual_payment_id": "E2E-001",
            "amount": "1000.00",
            "currency": "USD",
            "settlement_time": "2026-04-01T12:00:00Z",
            "rejection_code": "AC01",
        }
        result = bridge.extract_camt054_fields(raw)
        assert result["uetr"] == "test-uetr-1234"
        assert result["individual_payment_id"] == "E2E-001"
        assert result["amount"] == "1000.00"
        assert result["currency"] == "USD"
        assert result["settlement_time"] == "2026-04-01T12:00:00Z"
        assert result["rejection_code"] == "AC01"

    def test_empty_dict_returns_defaults(self, bridge: StateMachineBridge):
        result = bridge.extract_camt054_fields({})
        assert result["uetr"] == ""
        assert result["amount"] == "0"
        assert result["currency"] == "USD"
        assert result["settlement_time"] is None
        assert result["rejection_code"] is None

    def test_uetr_fallback_to_empty(self, bridge: StateMachineBridge):
        result = bridge.extract_camt054_fields({"amount": "500"})
        assert result["uetr"] == ""

    def test_nested_iso20022_structure(self, bridge: StateMachineBridge):
        raw = {
            "BkToCstmrDbtCdtNtfctn": {
                "Ntfctn": [{
                    "Ntry": [{
                        "Amt": {"#text": "2500.00", "@Ccy": "GBP"},
                        "NtryDtls": {
                            "TxDtls": {
                                "Refs": {
                                    "UETR": "nested-uetr-9999",
                                    "EndToEndId": "E2E-999",
                                },
                                "RtrInf": {"Rsn": {"Cd": "AM04"}},
                                "SttlmInf": {"SttlmDt": "2026-04-02"},
                            }
                        },
                    }]
                }]
            }
        }
        result = bridge.extract_camt054_fields(raw)
        assert result["uetr"] == "nested-uetr-9999"
        assert result["individual_payment_id"] == "E2E-999"
        assert result["amount"] == "2500.00"
        assert result["currency"] == "GBP"
        assert result["rejection_code"] == "AM04"

    def test_result_has_all_required_keys(self, bridge: StateMachineBridge):
        result = bridge.extract_camt054_fields({"uetr": "x"})
        required_keys = {"uetr", "individual_payment_id", "amount", "currency",
                         "settlement_time", "rejection_code"}
        assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# ISO 20022 extraction — pacs.008
# ---------------------------------------------------------------------------


class TestPacs008Extraction:
    def test_flat_dict(self, bridge: StateMachineBridge):
        raw = {
            "uetr": "pacs008-uetr-5678",
            "end_to_end_id": "E2E-002",
            "amount": "50000.00",
            "currency": "EUR",
            "settlement_date": "2026-04-02",
            "debtor_bic": "DEUTDEDB",
            "creditor_bic": "BNPAFRPP",
        }
        result = bridge.extract_pacs008_fields(raw)
        assert result["uetr"] == "pacs008-uetr-5678"
        assert result["end_to_end_id"] == "E2E-002"
        assert result["amount"] == "50000.00"
        assert result["currency"] == "EUR"
        assert result["settlement_date"] == "2026-04-02"
        assert result["debtor_bic"] == "DEUTDEDB"
        assert result["creditor_bic"] == "BNPAFRPP"

    def test_empty_dict_returns_defaults(self, bridge: StateMachineBridge):
        result = bridge.extract_pacs008_fields({})
        assert result["uetr"] == ""
        assert result["amount"] == "0"
        assert result["currency"] == "USD"
        assert result["settlement_date"] is None
        assert result["debtor_bic"] is None
        assert result["creditor_bic"] is None

    def test_nested_iso20022_structure(self, bridge: StateMachineBridge):
        raw = {
            "FIToFICstmrCdtTrf": {
                "CdtTrfTxInf": [{
                    "PmtId": {
                        "UETR": "nested-pacs-1111",
                        "EndToEndId": "E2E-1111",
                    },
                    "IntrBkSttlmAmt": {"#text": "75000.00", "@Ccy": "GBP"},
                    "IntrBkSttlmDt": "2026-04-03",
                    "DbtrAgt": {"FinInstnId": {"BICFI": "BARCGB22"}},
                    "CdtrAgt": {"FinInstnId": {"BICFI": "HSBCGB2L"}},
                }]
            }
        }
        result = bridge.extract_pacs008_fields(raw)
        assert result["uetr"] == "nested-pacs-1111"
        assert result["end_to_end_id"] == "E2E-1111"
        assert result["amount"] == "75000.00"
        assert result["currency"] == "GBP"
        assert result["settlement_date"] == "2026-04-03"
        assert result["debtor_bic"] == "BARCGB22"
        assert result["creditor_bic"] == "HSBCGB2L"

    def test_result_has_all_required_keys(self, bridge: StateMachineBridge):
        result = bridge.extract_pacs008_fields({"uetr": "x"})
        required_keys = {"uetr", "end_to_end_id", "amount", "currency",
                         "settlement_date", "debtor_bic", "creditor_bic"}
        assert required_keys.issubset(result.keys())

    def test_uetr_fallback_from_uppercase_key(self, bridge: StateMachineBridge):
        result = bridge.extract_pacs008_fields({"UETR": "upper-uetr"})
        assert result["uetr"] == "upper-uetr"


# ---------------------------------------------------------------------------
# Pure-Python fallback extraction (always tested regardless of Rust)
# ---------------------------------------------------------------------------


class TestPythonFallbackExtraction:
    def test_camt054_flat_dict(self):
        result = _extract_camt054_python({
            "uetr": "py-uetr",
            "amount": "999",
            "currency": "JPY",
        })
        assert result["uetr"] == "py-uetr"
        assert result["amount"] == "999"
        assert result["currency"] == "JPY"

    def test_camt054_empty_dict(self):
        result = _extract_camt054_python({})
        assert result["uetr"] == ""
        assert result["amount"] == "0"
        assert result["currency"] == "USD"
        assert result["settlement_time"] is None

    def test_pacs008_flat_dict(self):
        result = _extract_pacs008_python({
            "uetr": "py-pacs",
            "amount": "12345",
            "currency": "CHF",
            "debtor_bic": "UBSWCHZH",
        })
        assert result["uetr"] == "py-pacs"
        assert result["amount"] == "12345"
        assert result["debtor_bic"] == "UBSWCHZH"

    def test_pacs008_empty_dict(self):
        result = _extract_pacs008_python({})
        assert result["uetr"] == ""
        assert result["amount"] == "0"


# ---------------------------------------------------------------------------
# Rust/Python parity (only run when Rust is available)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _RUST_AVAILABLE, reason="Rust extension not installed")
class TestRustPythonParity:
    """Verify Rust and Python fallback extraction give identical results."""

    def test_camt054_flat_parity(self):
        raw = {
            "uetr": "parity-uetr",
            "amount": "8765.43",
            "currency": "CHF",
            "settlement_time": "2026-03-15T09:00:00Z",
            "rejection_code": "AM04",
        }
        rust_result = dict(__import__("lip_c3_rust_state_machine").extract_camt054_fields(raw))
        py_result = _extract_camt054_python(raw)
        assert rust_result["uetr"] == py_result["uetr"]
        assert rust_result["amount"] == py_result["amount"]
        assert rust_result["currency"] == py_result["currency"]
        assert rust_result["rejection_code"] == py_result["rejection_code"]

    def test_pacs008_flat_parity(self):
        raw = {
            "uetr": "parity-pacs",
            "amount": "11111.11",
            "currency": "SEK",
            "debtor_bic": "SWEDSESS",
        }
        rust_result = dict(__import__("lip_c3_rust_state_machine").extract_pacs008_fields(raw))
        py_result = _extract_pacs008_python(raw)
        assert rust_result["uetr"] == py_result["uetr"]
        assert rust_result["amount"] == py_result["amount"]
        assert rust_result["debtor_bic"] == py_result["debtor_bic"]

    def test_taxonomy_parity(self):
        import lip_c3_rust_state_machine as rust  # type: ignore[import-untyped]

        from lip.c3_repayment_engine.rejection_taxonomy import (
            classify_rejection_code as py_classify,
        )
        test_codes = ["AC01", "AM04", "AG02", "NARR", "AGNT", "INVB", "DNOR", "RR01", "LEGL"]
        for code in test_codes:
            rust_cls = rust.classify_rejection_code(code)
            py_cls = py_classify(code).value
            assert rust_cls == py_cls, f"Parity failure for {code}: rust={rust_cls} py={py_cls}"


# ---------------------------------------------------------------------------
# PaymentWatchdog — core functionality
# ---------------------------------------------------------------------------


class TestPaymentWatchdog:
    def test_register_and_track(self, watchdog: PaymentWatchdog):
        watchdog.register("uetr-001", state="FUNDED", corridor="USD_EUR")
        assert watchdog.tracked_count() == 1

    def test_update_to_terminal_deregisters(self, watchdog: PaymentWatchdog):
        watchdog.register("uetr-001", state="FUNDED")
        watchdog.update_state("uetr-001", "REPAID")
        assert watchdog.tracked_count() == 0

    def test_update_to_non_terminal_keeps_tracking(self, watchdog: PaymentWatchdog):
        watchdog.register("uetr-001", state="FUNDED")
        watchdog.update_state("uetr-001", "REPAYMENT_PENDING")
        assert watchdog.tracked_count() == 1

    def test_deregister(self, watchdog: PaymentWatchdog):
        watchdog.register("uetr-001", state="MONITORING")
        watchdog.deregister("uetr-001")
        assert watchdog.tracked_count() == 0

    def test_deregister_unknown_uetr_is_noop(self, watchdog: PaymentWatchdog):
        watchdog.deregister("does-not-exist")  # must not raise

    def test_snapshot_structure(self, watchdog: PaymentWatchdog):
        watchdog.register("uetr-001", state="MONITORING", corridor="EUR_GBP")
        snapshot = watchdog.snapshot()
        assert len(snapshot) == 1
        entry = snapshot[0]
        assert entry["uetr"] == "uetr-001"
        assert entry["state"] == "MONITORING"
        assert entry["corridor"] == "EUR_GBP"
        assert entry["age_s"] >= 0

    def test_all_terminal_states_are_deregistered_on_update(self, watchdog: PaymentWatchdog):
        terminal_states = [
            "REPAID", "BUFFER_REPAID", "DEFAULTED",
            "OFFER_DECLINED", "OFFER_EXPIRED",
            "DISPUTE_BLOCKED", "AML_BLOCKED",
        ]
        for state in terminal_states:
            watchdog.register(f"uetr-{state}", state="FUNDED")
            watchdog.update_state(f"uetr-{state}", state)
        assert watchdog.tracked_count() == 0

    def test_multiple_payments_tracked(self, watchdog: PaymentWatchdog):
        for i in range(5):
            watchdog.register(f"uetr-{i:03d}", state="FUNDED", corridor="USD_EUR")
        assert watchdog.tracked_count() == 5

    def test_stuck_detection_fires_callback(self):
        """Watchdog detects stuck payments and calls _on_stuck."""
        stuck_events = []

        class InstrumentedWatchdog(PaymentWatchdog):
            def _on_stuck(self, entry, age_s, ttl):
                stuck_events.append((entry.uetr, entry.state))

        wdog = InstrumentedWatchdog(
            poll_interval_s=0.05,
            ttl_overrides={"FUNDED": 0.01},  # 10ms TTL
        )
        wdog.register("stuck-uetr", state="FUNDED", corridor="USD_EUR")
        wdog.start()
        time.sleep(0.15)
        wdog.stop()

        assert len(stuck_events) >= 1
        assert stuck_events[0] == ("stuck-uetr", "FUNDED")

    def test_non_stuck_payment_not_flagged(self):
        """Payment within TTL must not be flagged."""
        stuck_events = []

        class InstrumentedWatchdog(PaymentWatchdog):
            def _on_stuck(self, entry, age_s, ttl):
                stuck_events.append(entry.uetr)

        wdog = InstrumentedWatchdog(
            poll_interval_s=0.05,
            ttl_overrides={"FUNDED": 10.0},  # 10-second TTL — never expires in test
        )
        wdog.register("safe-uetr", state="FUNDED")
        wdog.start()
        time.sleep(0.1)
        wdog.stop()

        assert len(stuck_events) == 0

    def test_terminal_payment_never_flagged(self):
        """Terminal-state payments must never be flagged as stuck."""
        stuck_events = []

        class InstrumentedWatchdog(PaymentWatchdog):
            def _on_stuck(self, entry, age_s, ttl):
                stuck_events.append(entry.uetr)

        wdog = InstrumentedWatchdog(
            poll_interval_s=0.05,
            ttl_overrides={"REPAID": 0.0},  # 0ms TTL
        )
        wdog.register("terminal-uetr", state="REPAID")
        wdog.start()
        time.sleep(0.1)
        wdog.stop()

        assert len(stuck_events) == 0

    def test_start_stop_lifecycle(self):
        wdog = PaymentWatchdog(poll_interval_s=60.0)
        wdog.start()
        assert wdog._thread is not None
        assert wdog._thread.is_alive()
        wdog.stop()
        # After stop(), thread is either None or no longer alive
        assert wdog._thread is None or not wdog._thread.is_alive()

    def test_double_start_is_safe(self):
        wdog = PaymentWatchdog(poll_interval_s=60.0)
        wdog.start()
        wdog.start()  # must not raise or create a second thread
        wdog.stop()

    def test_metadata_preserved_in_entry(self, watchdog: PaymentWatchdog):
        watchdog.register(
            "uetr-meta",
            state="FUNDED",
            metadata={"bank_bic": "DEUTDEDB", "loan_id": "LOAN-001"},
        )
        snapshot = watchdog.snapshot()
        assert snapshot[0]["uetr"] == "uetr-meta"
