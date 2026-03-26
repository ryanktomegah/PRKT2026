"""
cancellation_detector.py — Adversarial camt.056 / pacs.004 cancellation detection.

Structural vulnerability: sender initiates payment → LIP bridges → sender recalls
via camt.056 (FIToFICstmrCdtTrf cancellation request). Bridge loan is now
uncollectible. Any sophisticated bank treasury will identify this in due diligence.

Detection approach:
  1. Track time between RJCT and camt.056 — short intervals are suspicious
  2. Track sender recall history — repeated recalls indicate pattern
  3. Flag for human review (conservative — do not auto-block)

ISO 20022 message types:
  - camt.056: FIToFI Payment Cancellation Request (sender-initiated recall)
  - pacs.004: Payment Return (receiver/intermediary-initiated return)

CIPHER sign-off required before any production deployment of cancellation scoring.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Metric names
METRIC_CANCELLATION_ALERTS = "lip_cancellation_alerts_total"
METRIC_CANCELLATION_SUSPICIOUS = "lip_cancellation_suspicious_total"

# Detection thresholds (CIPHER sign-off required to change)
# If a camt.056 arrives within this many seconds of the RJCT, it's suspicious
CANCELLATION_SUSPICION_WINDOW_SECONDS = 300  # 5 minutes

# Sender recall frequency: more than this many recalls in the lookback window
# triggers a behavioral alert
SENDER_RECALL_THRESHOLD = 3
SENDER_RECALL_LOOKBACK_SECONDS = 86400  # 24 hours

# Maximum tracked events per sender (memory bound)
MAX_RECALL_HISTORY_PER_SENDER = 100


@dataclass(frozen=True)
class CancellationEvent:
    """Normalised cancellation event from camt.056 or pacs.004.

    Attributes:
        uetr: UETR of the original payment being recalled.
        cancellation_type: "CAMT056" (sender recall) or "PACS004" (return).
        requesting_bic: BIC of the party requesting cancellation.
        reason_code: ISO 20022 cancellation reason (e.g., DUPL, FRAD, CUST).
        amount: Amount of the payment being recalled.
        currency: Currency code.
        timestamp: When the cancellation request was received.
        raw_source: Original message for audit.
    """
    uetr: str
    cancellation_type: str  # CAMT056 | PACS004
    requesting_bic: str
    reason_code: Optional[str]
    amount: Decimal
    currency: str
    timestamp: datetime
    raw_source: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CancellationAlert:
    """Alert emitted when a cancellation event is flagged as suspicious.

    Attributes:
        uetr: UETR of the affected payment / loan.
        alert_type: "RAPID_RECALL" | "REPEAT_SENDER" | "POST_FUNDING_RECALL".
        severity: "HIGH" | "MEDIUM" | "LOW".
        description: Human-readable description.
        cancellation_event: The triggering cancellation event.
        time_since_funding_seconds: Seconds between loan funding and recall.
        sender_recall_count_24h: Number of recalls by this sender in 24h.
        recommended_action: Always "HUMAN_REVIEW" (conservative).
        detected_at: Unix timestamp of detection.
    """
    uetr: str
    alert_type: str
    severity: str
    description: str
    cancellation_event: CancellationEvent
    time_since_funding_seconds: Optional[float]
    sender_recall_count_24h: int
    recommended_action: str = "HUMAN_REVIEW"
    detected_at: float = 0.0


class CancellationDetector:
    """Detects adversarial payment cancellation patterns.

    Monitors camt.056 (sender recall) and pacs.004 (payment return)
    messages and correlates them with active loan positions to identify
    potential cancellation attacks.

    Conservative approach: all suspicious cancellations are flagged for
    human review. No automated blocking.

    Parameters
    ----------
    suspicion_window_seconds:
        Time window after funding within which a recall is considered
        suspicious. Default: 300s (5 minutes).
    sender_recall_threshold:
        Number of recalls by the same sender in 24h that triggers a
        behavioral alert.
    metrics_collector:
        Optional Prometheus metrics collector.
    """

    def __init__(
        self,
        suspicion_window_seconds: int = CANCELLATION_SUSPICION_WINDOW_SECONDS,
        sender_recall_threshold: int = SENDER_RECALL_THRESHOLD,
        metrics_collector=None,
    ) -> None:
        self._suspicion_window = suspicion_window_seconds
        self._sender_threshold = sender_recall_threshold
        self._metrics = metrics_collector
        self._lock = threading.Lock()

        # Track funded loan timestamps: uetr → funding_time (unix)
        self._funded_loans: Dict[str, float] = {}

        # Track sender recall history: bic → deque of (timestamp, uetr)
        self._sender_recalls: Dict[str, Deque[Tuple[float, str]]] = defaultdict(
            lambda: deque(maxlen=MAX_RECALL_HISTORY_PER_SENDER)
        )

    def register_funding(self, uetr: str, funded_at: Optional[datetime] = None) -> None:
        """Register that a loan has been funded for a given UETR.

        Must be called when C7 issues a FUNDED decision so the detector
        can correlate subsequent cancellation requests.
        """
        ts = (funded_at or datetime.now(timezone.utc)).timestamp()
        with self._lock:
            self._funded_loans[uetr] = ts

    def deregister_funding(self, uetr: str) -> None:
        """Remove a UETR from the funded loans registry (e.g. on repayment)."""
        with self._lock:
            self._funded_loans.pop(uetr, None)

    def process_cancellation(self, event: CancellationEvent) -> List[CancellationAlert]:
        """Process a cancellation event and return any alerts.

        Parameters
        ----------
        event:
            Normalised cancellation event from C5 event normalizer.

        Returns
        -------
        List[CancellationAlert]
            Zero or more alerts. In the conservative approach, suspicious
            events always recommend HUMAN_REVIEW, never auto-block.
        """
        now = time.time()
        alerts: List[CancellationAlert] = []

        # Record sender recall history
        with self._lock:
            self._sender_recalls[event.requesting_bic].append((now, event.uetr))

            # Check if this UETR has an active funded loan
            funding_time = self._funded_loans.get(event.uetr)

        # 1. Post-funding recall check
        time_since_funding = None
        if funding_time is not None:
            time_since_funding = now - funding_time

            # Rapid recall: cancellation arrives very quickly after funding
            if time_since_funding < self._suspicion_window:
                alert = CancellationAlert(
                    uetr=event.uetr,
                    alert_type="RAPID_RECALL",
                    severity="HIGH",
                    description=(
                        f"camt.056 recall received {time_since_funding:.0f}s after loan funding. "
                        f"Possible adversarial cancellation attack. "
                        f"Sender: {event.requesting_bic}, Reason: {event.reason_code}"
                    ),
                    cancellation_event=event,
                    time_since_funding_seconds=time_since_funding,
                    sender_recall_count_24h=self._count_recent_recalls(event.requesting_bic),
                    detected_at=now,
                )
                alerts.append(alert)
                logger.warning(
                    "RAPID_RECALL alert: uetr=%s sender=%s time_since_funding=%.0fs",
                    event.uetr, event.requesting_bic, time_since_funding,
                )

            # Post-funding recall (not rapid, but still noteworthy)
            elif event.cancellation_type == "CAMT056":
                alert = CancellationAlert(
                    uetr=event.uetr,
                    alert_type="POST_FUNDING_RECALL",
                    severity="MEDIUM",
                    description=(
                        f"camt.056 recall received for funded loan. "
                        f"Time since funding: {time_since_funding / 3600:.1f}h. "
                        f"Sender: {event.requesting_bic}"
                    ),
                    cancellation_event=event,
                    time_since_funding_seconds=time_since_funding,
                    sender_recall_count_24h=self._count_recent_recalls(event.requesting_bic),
                    detected_at=now,
                )
                alerts.append(alert)

        # 2. Repeat sender check (regardless of funding status)
        recall_count = self._count_recent_recalls(event.requesting_bic)
        if recall_count >= self._sender_threshold:
            alert = CancellationAlert(
                uetr=event.uetr,
                alert_type="REPEAT_SENDER",
                severity="MEDIUM",
                description=(
                    f"Sender {event.requesting_bic} has submitted {recall_count} "
                    f"cancellation requests in the last 24h (threshold: {self._sender_threshold}). "
                    f"Possible pattern of adversarial behavior."
                ),
                cancellation_event=event,
                time_since_funding_seconds=time_since_funding,
                sender_recall_count_24h=recall_count,
                detected_at=now,
            )
            alerts.append(alert)
            logger.warning(
                "REPEAT_SENDER alert: bic=%s recall_count_24h=%d",
                event.requesting_bic, recall_count,
            )

        # Emit metrics
        if self._metrics and alerts:
            for alert in alerts:
                self._metrics.increment(
                    METRIC_CANCELLATION_ALERTS,
                    labels={"alert_type": alert.alert_type, "severity": alert.severity},
                )

        return alerts

    def _count_recent_recalls(self, bic: str) -> int:
        """Count recalls by a sender in the last 24 hours."""
        now = time.time()
        cutoff = now - SENDER_RECALL_LOOKBACK_SECONDS
        with self._lock:
            history = self._sender_recalls.get(bic, deque())
            return sum(1 for ts, _ in history if ts >= cutoff)

    def get_funded_loan_count(self) -> int:
        """Return the number of funded loans being monitored."""
        with self._lock:
            return len(self._funded_loans)


def normalize_camt056(msg: dict) -> CancellationEvent:
    """Parse a camt.056 FIToFI Payment Cancellation Request.

    ISO 20022 camt.056 structure:
      FIToFIPmtCxlReq → Assgnmt → Assgnr/Assgne
                       → Undrlyg → TxInf → OrgnlUETR, CxlRsnInf
    """
    underlying = msg.get("Undrlyg", msg.get("FIToFIPmtCxlReq", {}).get("Undrlyg", {}))
    tx_info = underlying.get("TxInf", msg.get("TxInf", {}))
    assgnmt = msg.get("Assgnmt", msg.get("FIToFIPmtCxlReq", {}).get("Assgnmt", {}))

    uetr = tx_info.get("OrgnlUETR", tx_info.get("OrgnlEndToEndId", msg.get("uetr", "")))

    reason_info = tx_info.get("CxlRsnInf", {})
    reason = reason_info.get("Rsn", {})
    reason_code = reason.get("Cd") if isinstance(reason, dict) else reason

    assgnr = assgnmt.get("Assgnr", {})
    requesting_bic = (
        assgnr.get("Agt", {}).get("FinInstnId", {}).get("BIC", "")
        or msg.get("requesting_bic", "")
    )

    amt_block = tx_info.get("OrgnlIntrBkSttlmAmt", {})
    if isinstance(amt_block, dict):
        amount = Decimal(str(amt_block.get("value", amt_block.get("Amt", "0"))))
        currency = amt_block.get("Ccy", "USD")
    else:
        amount = Decimal(str(amt_block)) if amt_block else Decimal("0")
        currency = msg.get("currency", "USD")

    ts_str = tx_info.get("CxlReqDt", assgnmt.get("CreDtTm", ""))
    try:
        timestamp = datetime.fromisoformat(str(ts_str)) if ts_str else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        timestamp = datetime.now(timezone.utc)

    return CancellationEvent(
        uetr=uetr,
        cancellation_type="CAMT056",
        requesting_bic=requesting_bic,
        reason_code=reason_code,
        amount=amount,
        currency=currency,
        timestamp=timestamp,
        raw_source=msg,
    )


def normalize_pacs004(msg: dict) -> CancellationEvent:
    """Parse a pacs.004 Payment Return message.

    ISO 20022 pacs.004 structure:
      PmtRtr → GrpHdr → MsgId, CreDtTm
             → TxInf → OrgnlUETR, RtrRsnInf
    """
    grp_hdr = msg.get("GrpHdr", msg.get("PmtRtr", {}).get("GrpHdr", {}))
    tx_info = msg.get("TxInf", msg.get("PmtRtr", {}).get("TxInf", {}))

    uetr = tx_info.get("OrgnlUETR", tx_info.get("OrgnlEndToEndId", msg.get("uetr", "")))

    reason_info = tx_info.get("RtrRsnInf", {})
    reason = reason_info.get("Rsn", {})
    reason_code = reason.get("Cd") if isinstance(reason, dict) else reason

    requesting_bic = (
        grp_hdr.get("InstgAgt", {}).get("FinInstnId", {}).get("BIC", "")
        or msg.get("requesting_bic", "")
    )

    amt_block = tx_info.get("RtrdIntrBkSttlmAmt", {})
    if isinstance(amt_block, dict):
        amount = Decimal(str(amt_block.get("value", amt_block.get("Amt", "0"))))
        currency = amt_block.get("Ccy", "USD")
    else:
        amount = Decimal(str(amt_block)) if amt_block else Decimal("0")
        currency = msg.get("currency", "USD")

    ts_str = grp_hdr.get("CreDtTm", "")
    try:
        timestamp = datetime.fromisoformat(str(ts_str)) if ts_str else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        timestamp = datetime.now(timezone.utc)

    return CancellationEvent(
        uetr=uetr,
        cancellation_type="PACS004",
        requesting_bic=requesting_bic,
        reason_code=reason_code,
        amount=amount,
        currency=currency,
        timestamp=timestamp,
        raw_source=msg,
    )
