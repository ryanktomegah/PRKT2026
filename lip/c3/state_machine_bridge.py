"""
state_machine_bridge.py — Python bridge to the Rust-backed C3 state machine core.

Architecture Spec v1.2 Sections S6, S7, S8.
See docs/specs/c3_state_machine_migration.md for full design rationale.

Layers:
1. StateMachineBridge — unified API over Rust (preferred) or pure Python (fallback).
   Falls back silently when the compiled Rust extension is not available (e.g. CI).

2. PaymentWatchdog — background watchdog thread.
   Flags payments stuck in non-terminal states beyond a configurable TTL.
   Emits Prometheus metric + fires PagerDuty Events API v2 alert.
"""
from __future__ import annotations

import logging
import threading
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

from lip.c3_repayment_engine.rejection_taxonomy import RejectionClass
from lip.c3_repayment_engine.rejection_taxonomy import classify_rejection_code as _py_classify
from lip.c3_repayment_engine.rejection_taxonomy import is_dispute_block as _py_is_block
from lip.c3_repayment_engine.rejection_taxonomy import maturity_days as _py_maturity_days_for_class
from lip.common.state_machines import InvalidTransitionError, PaymentState
from lip.common.state_machines import PaymentStateMachine as _PyPaymentStateMachine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt to import the compiled Rust extension
# ---------------------------------------------------------------------------

try:
    import lip_c3_rust_state_machine as _rust

    _RUST_AVAILABLE = True
    logger.debug(
        "lip_c3_rust_state_machine loaded (version %s): Rust-backed C3 core active.",
        getattr(_rust, "__version__", "unknown"),
    )
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False
    warnings.warn(
        "lip_c3_rust_state_machine Rust extension not found. "
        "Falling back to pure-Python C3 state machine implementations. "
        "Build the Rust extension with: "
        "cd lip/c3/rust_state_machine && maturin build && pip install target/wheels/*.whl",
        UserWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Managed payment state machine (unified interface)
# ---------------------------------------------------------------------------


class ManagedPaymentStateMachine:
    """Unified payment state machine backed by Rust or pure Python.

    Presents the same interface regardless of which backend is active:
      - .current_state: str
      - .is_terminal: bool
      - .transition(new_state: str) → None  (raises ValueError on illegal move)
      - .allowed_transitions() → list[str]

    This class is not instantiated directly — use StateMachineBridge.create_state_machine().
    """

    def __init__(self, initial_state: str = "MONITORING") -> None:
        if _RUST_AVAILABLE:
            self._backend = _rust.PaymentStateMachine(initial_state)
            self._use_rust = True
        else:
            try:
                py_state = PaymentState(initial_state)
            except ValueError:
                raise ValueError(f"Invalid PaymentState: '{initial_state}'") from None
            self._backend = _PyPaymentStateMachine(initial_state=py_state)
            self._use_rust = False

    @property
    def current_state(self) -> str:
        """The current payment state as a string."""
        if self._use_rust:
            return self._backend.current_state
        return self._backend.current_state.value

    @property
    def is_terminal(self) -> bool:
        """True when the machine has reached a terminal state."""
        return self._backend.is_terminal

    def transition(self, new_state: str) -> None:
        """Advance the machine to *new_state*.

        Raises:
            ValueError: If the transition is not permitted or new_state is unknown.
        """
        if self._use_rust:
            # Rust raises ValueError directly
            self._backend.transition(new_state)
        else:
            try:
                target = PaymentState(new_state)
            except ValueError:
                raise ValueError(f"Invalid PaymentState: '{new_state}'") from None
            try:
                self._backend.transition(target)
            except InvalidTransitionError as exc:
                raise ValueError(str(exc)) from exc

    def allowed_transitions(self) -> list[str]:
        """Return the list of state names reachable from the current state."""
        if self._use_rust:
            return list(self._backend.allowed_transitions())
        return [s.value for s in self._backend.allowed_transitions()]

    def __repr__(self) -> str:
        backend = "rust" if self._use_rust else "python"
        return (
            f"ManagedPaymentStateMachine("
            f"current_state={self.current_state!r}, "
            f"is_terminal={self.is_terminal}, "
            f"backend={backend!r})"
        )


# ---------------------------------------------------------------------------
# StateMachineBridge — unified API facade
# ---------------------------------------------------------------------------


class StateMachineBridge:
    """Unified API over the Rust-backed (or Python-fallback) C3 core.

    All public methods behave identically regardless of which backend is
    active. When the Rust extension is loaded, all operations go through
    the compiled `.so`; otherwise pure-Python implementations are used.

    Class attribute:
        RUST_AVAILABLE (bool): True when the Rust extension is loaded.
    """

    RUST_AVAILABLE: bool = _RUST_AVAILABLE

    # ── State machine factory ─────────────────────────────────────────────

    def create_state_machine(
        self,
        initial_state: str = "MONITORING",
    ) -> ManagedPaymentStateMachine:
        """Return a new ManagedPaymentStateMachine at *initial_state*.

        Raises:
            ValueError: If *initial_state* is not a valid PaymentState string.
        """
        return ManagedPaymentStateMachine(initial_state=initial_state)

    # ── Rejection taxonomy ────────────────────────────────────────────────

    def classify_rejection_code(self, code: str) -> str:
        """Return the rejection class name for an ISO 20022 rejection code.

        Returns one of: "CLASS_A", "CLASS_B", "CLASS_C", "BLOCK".

        Raises:
            ValueError: For codes not in the taxonomy.
        """
        if _RUST_AVAILABLE:
            return _rust.classify_rejection_code(code)
        rc = _py_classify(code)
        return rc.value

    def maturity_days(self, rejection_class: str) -> int:
        """Return the maturity window in days for a rejection class string.

        Args:
            rejection_class: One of "CLASS_A", "CLASS_B", "CLASS_C", "BLOCK".

        Returns:
            int: Maturity days (3, 7, 21, or 0).

        Raises:
            ValueError: For unknown class strings.
        """
        if _RUST_AVAILABLE:
            return int(_rust.maturity_days_for_class(rejection_class))
        try:
            rc = RejectionClass(rejection_class)
        except ValueError:
            raise ValueError(
                f"Unknown rejection class: '{rejection_class}'. "
                "Must be one of CLASS_A, CLASS_B, CLASS_C, BLOCK."
            ) from None
        return _py_maturity_days_for_class(rc)

    def is_block_code(self, code: str) -> bool:
        """Return True if *code* maps to the BLOCK rejection class.

        Returns False for unknown codes — never raises.
        """
        if _RUST_AVAILABLE:
            return _rust.is_block_code(code)
        return _py_is_block(code)

    # ── ISO 20022 field extraction ────────────────────────────────────────

    def extract_camt054_fields(self, raw_message: dict) -> dict:
        """Extract normalised fields from a camt.054 dict.

        Accepts both nested ISO 20022 key structure and flat dicts (used
        by test/mock payloads).

        Returns:
            dict with keys: uetr, individual_payment_id, amount, currency,
                settlement_time (str|None), rejection_code (str|None).

        Raises:
            ValueError: On parse failure.
        """
        if _RUST_AVAILABLE:
            return dict(_rust.extract_camt054_fields(raw_message))
        return _extract_camt054_python(raw_message)

    def extract_pacs008_fields(self, raw_message: dict) -> dict:
        """Extract normalised fields from a pacs.008 dict.

        Returns:
            dict with keys: uetr, end_to_end_id, amount, currency,
                settlement_date (str|None), debtor_bic (str|None),
                creditor_bic (str|None).

        Raises:
            ValueError: On parse failure.
        """
        if _RUST_AVAILABLE:
            return dict(_rust.extract_pacs008_fields(raw_message))
        return _extract_pacs008_python(raw_message)


# ---------------------------------------------------------------------------
# Pure-Python extraction fallbacks (mirror settlement_handlers.py logic)
# ---------------------------------------------------------------------------


def _extract_camt054_python(raw_message: dict) -> dict:
    """Pure-Python camt.054 field extraction (fallback when Rust unavailable)."""
    try:
        notification = (
            raw_message.get("BkToCstmrDbtCdtNtfctn", raw_message)
            .get("Ntfctn", [raw_message])[0]
        )
        entry = notification.get("Ntry", [{}])[0]
        txn_details = entry.get("NtryDtls", {}).get("TxDtls", {})

        uetr = (
            txn_details.get("Refs", {}).get("UETR")
            or raw_message.get("uetr", "")
        )
        individual_payment_id = (
            txn_details.get("Refs", {}).get("EndToEndId")
            or raw_message.get("individual_payment_id", uetr)
        )
        amount_raw = (
            entry.get("Amt", {}).get("#text")
            or entry.get("Amt")
            or raw_message.get("amount", "0")
        )
        currency = (
            entry.get("Amt", {}).get("@Ccy")
            or raw_message.get("currency", "USD")
        )
        settlement_time = (
            txn_details.get("SttlmInf", {}).get("SttlmDt")
            or raw_message.get("settlement_time")
        )
        rejection_code = (
            txn_details.get("RtrInf", {}).get("Rsn", {}).get("Cd")
            or raw_message.get("rejection_code")
        )
    except Exception as exc:
        raise ValueError(f"camt.054 field extraction failed: {exc}") from exc

    return {
        "uetr": uetr or "",
        "individual_payment_id": individual_payment_id or "",
        "amount": str(amount_raw),
        "currency": currency or "USD",
        "settlement_time": settlement_time,
        "rejection_code": rejection_code,
    }


def _extract_pacs008_python(raw_message: dict) -> dict:
    """Pure-Python pacs.008 field extraction (fallback when Rust unavailable)."""
    try:
        tx_info = (
            raw_message.get("FIToFICstmrCdtTrf", {})
            .get("CdtTrfTxInf", [{}])[0]
        )
        uetr = (
            tx_info.get("PmtId", {}).get("UETR")
            or raw_message.get("uetr")
            or raw_message.get("UETR", "")
        )
        end_to_end_id = (
            tx_info.get("PmtId", {}).get("EndToEndId")
            or raw_message.get("EndToEndId")
            or raw_message.get("end_to_end_id", uetr)
        )
        amt_node = tx_info.get("IntrBkSttlmAmt", {})
        if isinstance(amt_node, dict):
            amount = (
                amt_node.get("#text")
                or amt_node.get("amount")
                or raw_message.get("amount", "0")
            )
            currency = amt_node.get("@Ccy") or raw_message.get("currency", "USD")
        else:
            amount = raw_message.get("amount", "0")
            currency = raw_message.get("currency", "USD")
        settlement_date = (
            tx_info.get("IntrBkSttlmDt")
            or raw_message.get("settlement_date")
            or raw_message.get("IntrBkSttlmDt")
        )
        debtor_bic = (
            tx_info.get("DbtrAgt", {}).get("FinInstnId", {}).get("BICFI")
            or raw_message.get("debtor_bic")
        )
        creditor_bic = (
            tx_info.get("CdtrAgt", {}).get("FinInstnId", {}).get("BICFI")
            or raw_message.get("creditor_bic")
        )
    except Exception as exc:
        raise ValueError(f"pacs.008 field extraction failed: {exc}") from exc

    return {
        "uetr": uetr or "",
        "end_to_end_id": end_to_end_id or "",
        "amount": str(amount),
        "currency": currency or "USD",
        "settlement_date": settlement_date,
        "debtor_bic": debtor_bic,
        "creditor_bic": creditor_bic,
    }


# ---------------------------------------------------------------------------
# Watchdog timer — stuck-state detection and alerting
# ---------------------------------------------------------------------------

#: Default TTL (seconds) per non-terminal state.
#: Payments in a non-terminal state longer than their TTL are flagged as stuck.
#: Values are 2× the expected settlement window for each state class.
_DEFAULT_TTL_SECONDS: dict[str, float] = {
    "MONITORING": 6 * 86_400,           # 6 days  (2× Class A 3d maturity)
    "FAILURE_DETECTED": 6 * 86_400,     # 6 days
    "BRIDGE_OFFERED": 86_400,           # 24 hours (offer validity window)
    "FUNDED": 42 * 86_400,              # 42 days (2× Class C 21d maturity)
    "REPAYMENT_PENDING": 14 * 86_400,   # 14 days (2× Class B 7d maturity)
    "CANCELLATION_ALERT": 14 * 86_400,  # 14 days
}

#: Fallback TTL for states not listed in _DEFAULT_TTL_SECONDS (2× Class B 7d maturity).
_FALLBACK_TTL_SECONDS: float = 14 * 86_400

#: Terminal states — never flagged as stuck.
_TERMINAL_STATES = frozenset({
    "REPAID",
    "BUFFER_REPAID",
    "DEFAULTED",
    "OFFER_DECLINED",
    "OFFER_EXPIRED",
    "DISPUTE_BLOCKED",
    "AML_BLOCKED",
})


@dataclass
class WatchdogEntry:
    """A single payment tracked by the watchdog."""

    uetr: str
    state: str
    last_updated: float  # UNIX timestamp (time.monotonic or time.time)
    corridor: str = "UNKNOWN"
    metadata: dict = field(default_factory=dict)


class PaymentWatchdog:
    """Background thread that detects payments stuck in non-terminal states.

    Usage::

        watchdog = PaymentWatchdog(
            poll_interval_s=60,
            pagerduty_routing_key="your-key",  # optional
        )
        watchdog.start()

        # Register a payment to monitor:
        watchdog.register("uetr-abc123", state="FUNDED", corridor="USD_EUR")

        # Update state when a transition occurs:
        watchdog.update_state("uetr-abc123", "REPAID")

        # Stop on shutdown:
        watchdog.stop()

    Stuck payment detection:
        A payment is "stuck" if it remains in a non-terminal state for longer
        than `ttl_seconds[state]` (default: 2× the expected settlement window).

    Alerting:
        1. Prometheus counter ``lip_c3_stuck_payments_total`` (if prometheus_client
           is installed).
        2. PagerDuty Events API v2 trigger (if pagerduty_routing_key is set).
    """

    def __init__(
        self,
        poll_interval_s: float = 60.0,
        ttl_overrides: Optional[dict[str, float]] = None,
        pagerduty_routing_key: Optional[str] = None,
        pagerduty_events_url: str = "https://events.pagerduty.com/v2/enqueue",
    ) -> None:
        self._poll_interval = poll_interval_s
        self._ttl: dict[str, float] = {**_DEFAULT_TTL_SECONDS, **(ttl_overrides or {})}
        self._pagerduty_key = pagerduty_routing_key
        self._pagerduty_url = pagerduty_events_url

        self._lock = threading.Lock()
        self._payments: dict[str, WatchdogEntry] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Prometheus metrics (optional dependency)
        self._stuck_counter = _build_prometheus_counter()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the watchdog background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("PaymentWatchdog already running — ignoring start().")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="lip-c3-watchdog",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "PaymentWatchdog started (poll_interval=%.0fs, pagerduty=%s).",
            self._poll_interval,
            "enabled" if self._pagerduty_key else "disabled",
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the watchdog background thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("PaymentWatchdog stopped.")

    # ── Registry ──────────────────────────────────────────────────────────

    def register(
        self,
        uetr: str,
        state: str,
        corridor: str = "UNKNOWN",
        metadata: Optional[dict] = None,
    ) -> None:
        """Register a payment for watchdog monitoring.

        Args:
            uetr: Unique End-to-End Transaction Reference.
            state: Current PaymentState string.
            corridor: Corridor key (e.g. "USD_EUR") for labelling metrics.
            metadata: Arbitrary metadata stored alongside the entry.
        """
        with self._lock:
            self._payments[uetr] = WatchdogEntry(
                uetr=uetr,
                state=state,
                last_updated=time.monotonic(),
                corridor=corridor,
                metadata=metadata or {},
            )

    def update_state(self, uetr: str, new_state: str) -> None:
        """Update the recorded state for a payment.

        If the new state is terminal, the payment is deregistered from
        monitoring (no more stuck-state checks will be performed).

        Args:
            uetr: Payment identifier.
            new_state: New PaymentState string.
        """
        with self._lock:
            if uetr not in self._payments:
                return
            if new_state in _TERMINAL_STATES:
                del self._payments[uetr]
                logger.debug("Watchdog: %s reached terminal state %s — deregistered.", uetr, new_state)
                return
            entry = self._payments[uetr]
            entry.state = new_state
            entry.last_updated = time.monotonic()

    def deregister(self, uetr: str) -> None:
        """Remove a payment from watchdog monitoring."""
        with self._lock:
            self._payments.pop(uetr, None)

    # ── Background poll ───────────────────────────────────────────────────

    def _run(self) -> None:
        """Main watchdog loop. Runs until stop() is called."""
        while not self._stop_event.wait(timeout=self._poll_interval):
            self._check_all()

    def _check_all(self) -> None:
        """Check all registered payments for stuck-state violations."""
        now = time.monotonic()
        with self._lock:
            snapshot = list(self._payments.values())

        for entry in snapshot:
            if entry.state in _TERMINAL_STATES:
                continue
            ttl = self._ttl.get(entry.state, _DEFAULT_TTL_SECONDS.get(entry.state, _FALLBACK_TTL_SECONDS))
            age_s = now - entry.last_updated
            if age_s > ttl:
                self._on_stuck(entry, age_s, ttl)

    def _on_stuck(self, entry: WatchdogEntry, age_s: float, ttl: float) -> None:
        """Handle a payment detected as stuck.

        Emits Prometheus metric and fires PagerDuty alert.
        """
        age_h = age_s / 3600
        ttl_h = ttl / 3600
        logger.warning(
            "STUCK PAYMENT: uetr=%s state=%s corridor=%s age=%.1fh ttl=%.1fh",
            entry.uetr,
            entry.state,
            entry.corridor,
            age_h,
            ttl_h,
        )

        # Prometheus metric
        if self._stuck_counter is not None:
            try:
                self._stuck_counter.labels(
                    state=entry.state,
                    corridor=entry.corridor,
                ).inc()
            except Exception as exc:
                logger.debug("Prometheus increment failed: %s", exc)

        # PagerDuty alert
        if self._pagerduty_key:
            self._fire_pagerduty(entry, age_h, ttl_h)

    def _fire_pagerduty(
        self,
        entry: WatchdogEntry,
        age_h: float,
        ttl_h: float,
    ) -> None:
        """Fire a PagerDuty Events API v2 trigger for a stuck payment."""
        import json

        payload = {
            "routing_key": self._pagerduty_key,
            "event_action": "trigger",
            "dedup_key": f"lip-c3-stuck-{entry.uetr}",
            "payload": {
                "summary": (
                    f"LIP C3: payment {entry.uetr} stuck in {entry.state} "
                    f"for {age_h:.1f}h (TTL={ttl_h:.1f}h, corridor={entry.corridor})"
                ),
                "severity": "critical",
                "source": "lip-c3-watchdog",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "custom_details": {
                    "uetr": entry.uetr,
                    "state": entry.state,
                    "corridor": entry.corridor,
                    "age_hours": round(age_h, 2),
                    "ttl_hours": round(ttl_h, 2),
                    **entry.metadata,
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            self._pagerduty_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=5) as resp:
                logger.info(
                    "PagerDuty alert fired for %s (status=%d).", entry.uetr, resp.status
                )
        except URLError as exc:
            logger.error("PagerDuty alert failed for %s: %s", entry.uetr, exc)

    def tracked_count(self) -> int:
        """Return the number of payments currently being monitored."""
        with self._lock:
            return len(self._payments)

    def snapshot(self) -> list[dict]:
        """Return a serialisable snapshot of all tracked payments."""
        with self._lock:
            return [
                {
                    "uetr": e.uetr,
                    "state": e.state,
                    "age_s": time.monotonic() - e.last_updated,
                    "corridor": e.corridor,
                }
                for e in self._payments.values()
            ]


# ---------------------------------------------------------------------------
# Prometheus counter factory (optional — graceful no-op if not installed)
# ---------------------------------------------------------------------------

_PROMETHEUS_COUNTER = None
_PROMETHEUS_COUNTER_LOCK = threading.Lock()


def _build_prometheus_counter():
    """Return a module-level prometheus_client Counter singleton, or None if unavailable.

    Uses a module-level singleton to avoid duplicate registration errors when
    multiple PaymentWatchdog instances are created in the same process.
    """
    global _PROMETHEUS_COUNTER
    if _PROMETHEUS_COUNTER is not None:
        return _PROMETHEUS_COUNTER
    try:
        from prometheus_client import Counter

        with _PROMETHEUS_COUNTER_LOCK:
            if _PROMETHEUS_COUNTER is None:
                _PROMETHEUS_COUNTER = Counter(
                    "lip_c3_stuck_payments_total",
                    "Payments flagged as stuck in a non-terminal state beyond their TTL",
                    ["state", "corridor"],
                )
        return _PROMETHEUS_COUNTER
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Module-level singleton (optional convenience)
# ---------------------------------------------------------------------------

#: Default bridge instance — ready to use without explicit instantiation.
default_bridge = StateMachineBridge()
