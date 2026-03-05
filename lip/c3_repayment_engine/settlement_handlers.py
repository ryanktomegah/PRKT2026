"""
settlement_handlers.py — All 5 settlement signal handlers
Architecture Spec S2.3:
  1. SWIFT camt.054
  2. FedNow
  3. RTP
  4. SEPA
  5. Buffer (internal settlement)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SettlementRail(str, Enum):
    SWIFT = "SWIFT"
    FEDNOW = "FEDNOW"
    RTP = "RTP"
    SEPA = "SEPA"
    BUFFER = "BUFFER"


@dataclass
class SettlementSignal:
    """Normalised settlement signal produced by any rail handler."""

    uetr: str
    individual_payment_id: str
    rail: SettlementRail
    amount: Decimal
    currency: str
    settlement_time: datetime
    raw_message: dict
    rejection_code: Optional[str] = None


@dataclass
class SettlementResult:
    """Outcome of processing a SettlementSignal against an active loan."""

    signal: SettlementSignal
    is_settled: bool
    settlement_amount: Decimal
    rejection_class: Optional[str] = None
    maturity_days: Optional[int] = None
    bridge_eligible: bool = True


# ── Helper ───────────────────────────────────────────────────────────────────

def _parse_decimal(value) -> Decimal:
    """Safely coerce a value to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _parse_datetime(value) -> datetime:
    """Return a timezone-aware datetime from an ISO string or pass-through."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Rail handlers ─────────────────────────────────────────────────────────────

class SWIFTCamt054Handler:
    """Parses SWIFT camt.054 BankToCustomerDebitCreditNotification messages."""

    def handle(self, raw_camt054: dict) -> SettlementSignal:
        """Parse a camt.054 dict and return a normalised SettlementSignal.

        Expected top-level keys (ISO 20022 JSON representation):
          BkToCstmrDbtCdtNtfctn → Ntfctn[0] → Ntry[0]
        Falls back gracefully to flat dict keys for test/mock payloads.
        """
        try:
            notification = (
                raw_camt054
                .get("BkToCstmrDbtCdtNtfctn", raw_camt054)
                .get("Ntfctn", [raw_camt054])[0]
            )
            entry = notification.get("Ntry", [{}])[0]
            txn_details = entry.get("NtryDtls", {}).get("TxDtls", {})

            uetr = self.extract_uetr(raw_camt054)
            settlement_info = self.extract_settlement_info(raw_camt054)

            amount_raw = (
                entry.get("Amt", {}).get("#text")
                or entry.get("Amt")
                or raw_camt054.get("amount", "0")
            )
            currency = (
                entry.get("Amt", {}).get("@Ccy")
                or raw_camt054.get("currency", "USD")
            )
            rejection_code = (
                txn_details.get("RtrInf", {}).get("Rsn", {}).get("Cd")
                or raw_camt054.get("rejection_code")
            )
            individual_payment_id = (
                txn_details.get("Refs", {}).get("EndToEndId")
                or raw_camt054.get("individual_payment_id", uetr)
            )
            settlement_time_raw = (
                settlement_info.get("SttlmDt")
                or raw_camt054.get("settlement_time")
            )
            settlement_time = (
                _parse_datetime(settlement_time_raw)
                if settlement_time_raw
                else _utcnow()
            )
        except Exception as exc:
            logger.exception("Failed to parse camt.054 message: %s", exc)
            raise ValueError(f"Invalid camt.054 payload: {exc}") from exc

        return SettlementSignal(
            uetr=uetr,
            individual_payment_id=individual_payment_id,
            rail=SettlementRail.SWIFT,
            amount=_parse_decimal(amount_raw),
            currency=currency,
            settlement_time=settlement_time,
            raw_message=raw_camt054,
            rejection_code=rejection_code,
        )

    def extract_uetr(self, msg: dict) -> str:
        """Extract the UETR from a camt.054 message.

        Checks standard ISO 20022 path first, then flat key fallback.
        """
        try:
            notification = (
                msg.get("BkToCstmrDbtCdtNtfctn", msg)
                   .get("Ntfctn", [msg])[0]
            )
            entry = notification.get("Ntry", [{}])[0]
            uetr = (
                entry.get("NtryDtls", {})
                     .get("TxDtls", {})
                     .get("Refs", {})
                     .get("UETR")
            )
        except (AttributeError, IndexError):
            uetr = None

        return uetr or msg.get("uetr", "")

    def extract_settlement_info(self, msg: dict) -> dict:
        """Return the settlement date/time block from a camt.054 message."""
        try:
            notification = (
                msg.get("BkToCstmrDbtCdtNtfctn", msg)
                   .get("Ntfctn", [msg])[0]
            )
            entry = notification.get("Ntry", [{}])[0]
            return entry.get("NtryDtls", {}).get("TxDtls", {}).get("SttlmInf", {})
        except (AttributeError, IndexError):
            return {}


class FedNowHandler:
    """Parses FedNow ISO 20022 pacs.002 / credit transfer settlement messages."""

    def handle(self, raw_message: dict) -> SettlementSignal:
        """Parse a FedNow message dict and return a normalised SettlementSignal."""
        try:
            uetr = raw_message.get("uetr") or raw_message.get("UETR", "")
            individual_payment_id = (
                raw_message.get("EndToEndId")
                or raw_message.get("individual_payment_id", uetr)
            )
            amount_raw = raw_message.get("IntrBkSttlmAmt", {})
            if isinstance(amount_raw, dict):
                amount = _parse_decimal(amount_raw.get("#text", "0"))
                currency = amount_raw.get("@Ccy", "USD")
            else:
                amount = _parse_decimal(raw_message.get("amount", "0"))
                currency = raw_message.get("currency", "USD")

            settlement_time_raw = raw_message.get("IntrBkSttlmDt") or raw_message.get("settlement_time")
            settlement_time = (
                _parse_datetime(settlement_time_raw)
                if settlement_time_raw
                else _utcnow()
            )
            rejection_code = (
                raw_message.get("TxSts", {}).get("RsnInf", {}).get("Rsn", {}).get("Cd")
                if isinstance(raw_message.get("TxSts"), dict)
                else raw_message.get("rejection_code")
            )
        except Exception as exc:
            logger.exception("Failed to parse FedNow message: %s", exc)
            raise ValueError(f"Invalid FedNow payload: {exc}") from exc

        return SettlementSignal(
            uetr=uetr,
            individual_payment_id=individual_payment_id,
            rail=SettlementRail.FEDNOW,
            amount=amount,
            currency=currency,
            settlement_time=settlement_time,
            raw_message=raw_message,
            rejection_code=rejection_code,
        )


class RTPHandler:
    """Parses RTP (The Clearing House Real-Time Payments) messages."""

    def handle(self, raw_message: dict) -> SettlementSignal:
        """Parse an RTP message dict and return a normalised SettlementSignal."""
        try:
            end_to_end_id = self.extract_end_to_end_id(raw_message)
            uetr = raw_message.get("uetr") or raw_message.get("UETR") or end_to_end_id

            amount_raw = raw_message.get("TxInf", {}).get("IntrBkSttlmAmt", {})
            if isinstance(amount_raw, dict):
                amount = _parse_decimal(amount_raw.get("#text", "0"))
                currency = amount_raw.get("@Ccy", "USD")
            else:
                amount = _parse_decimal(raw_message.get("amount", "0"))
                currency = raw_message.get("currency", "USD")

            settlement_time_raw = (
                raw_message.get("TxInf", {}).get("IntrBkSttlmDt")
                or raw_message.get("settlement_time")
            )
            settlement_time = (
                _parse_datetime(settlement_time_raw)
                if settlement_time_raw
                else _utcnow()
            )
            rejection_code = raw_message.get("rejection_code")
        except Exception as exc:
            logger.exception("Failed to parse RTP message: %s", exc)
            raise ValueError(f"Invalid RTP payload: {exc}") from exc

        return SettlementSignal(
            uetr=uetr,
            individual_payment_id=end_to_end_id,
            rail=SettlementRail.RTP,
            amount=amount,
            currency=currency,
            settlement_time=settlement_time,
            raw_message=raw_message,
            rejection_code=rejection_code,
        )

    def extract_end_to_end_id(self, msg: dict) -> str:
        """Extract the EndToEndId used for UETR mapping in RTP messages."""
        return (
            msg.get("TxInf", {}).get("PmtId", {}).get("EndToEndId")
            or msg.get("EndToEndId")
            or msg.get("individual_payment_id", "")
        )


class SEPAHandler:
    """Parses SEPA Credit Transfer / Direct Debit settlement messages (pacs.002)."""

    def handle(self, raw_message: dict) -> SettlementSignal:
        """Parse a SEPA message dict and return a normalised SettlementSignal."""
        try:
            uetr = raw_message.get("uetr") or raw_message.get("UETR", "")
            individual_payment_id = (
                raw_message.get("OrgnlEndToEndId")
                or raw_message.get("EndToEndId")
                or raw_message.get("individual_payment_id", uetr)
            )
            amount_raw = raw_message.get("TxInf", {}).get("IntrBkSttlmAmt", {})
            if isinstance(amount_raw, dict):
                amount = _parse_decimal(amount_raw.get("#text", "0"))
                currency = amount_raw.get("@Ccy", "EUR")
            else:
                amount = _parse_decimal(raw_message.get("amount", "0"))
                currency = raw_message.get("currency", "EUR")

            settlement_time_raw = (
                raw_message.get("TxInf", {}).get("IntrBkSttlmDt")
                or raw_message.get("settlement_time")
            )
            settlement_time = (
                _parse_datetime(settlement_time_raw)
                if settlement_time_raw
                else _utcnow()
            )
            rejection_code = (
                raw_message.get("TxInf", {})
                           .get("StsRsnInf", {})
                           .get("Rsn", {})
                           .get("Cd")
                if isinstance(raw_message.get("TxInf"), dict)
                else raw_message.get("rejection_code")
            )
        except Exception as exc:
            logger.exception("Failed to parse SEPA message: %s", exc)
            raise ValueError(f"Invalid SEPA payload: {exc}") from exc

        return SettlementSignal(
            uetr=uetr,
            individual_payment_id=individual_payment_id,
            rail=SettlementRail.SEPA,
            amount=amount,
            currency=currency,
            settlement_time=settlement_time,
            raw_message=raw_message,
            rejection_code=rejection_code,
        )


class BufferSettlementHandler:
    """Handles internal corridor buffer settlements (Architecture Spec S11.4).

    Buffer settlements occur when the external rail has not confirmed within the
    maturity window and the CorridorBuffer issues an internal settlement signal.
    """

    def handle(self, raw_message: dict) -> SettlementSignal:
        """Parse an internal buffer settlement message."""
        try:
            uetr = raw_message.get("uetr", "")
            individual_payment_id = raw_message.get("individual_payment_id", uetr)
            amount = _parse_decimal(raw_message.get("amount", "0"))
            currency = raw_message.get("currency", "USD")
            settlement_time_raw = raw_message.get("settlement_time")
            settlement_time = (
                _parse_datetime(settlement_time_raw)
                if settlement_time_raw
                else _utcnow()
            )
            rejection_code = raw_message.get("rejection_code")
        except Exception as exc:
            logger.exception("Failed to parse buffer settlement message: %s", exc)
            raise ValueError(f"Invalid buffer settlement payload: {exc}") from exc

        logger.info(
            "Buffer settlement processed: uetr=%s amount=%s %s",
            uetr, amount, currency,
        )
        return SettlementSignal(
            uetr=uetr,
            individual_payment_id=individual_payment_id,
            rail=SettlementRail.BUFFER,
            amount=amount,
            currency=currency,
            settlement_time=settlement_time,
            raw_message=raw_message,
            rejection_code=rejection_code,
        )


# ── Registry ──────────────────────────────────────────────────────────────────

class SettlementHandlerRegistry:
    """Dispatches raw settlement messages to the appropriate rail handler."""

    def __init__(self) -> None:
        self._handlers: dict[SettlementRail, object] = {}

    def register(self, rail: SettlementRail, handler) -> None:
        """Register a handler for the given settlement rail."""
        self._handlers[rail] = handler
        logger.debug("Registered handler %s for rail %s", type(handler).__name__, rail)

    def dispatch(self, rail: SettlementRail, raw_message: dict) -> SettlementSignal:
        """Dispatch a raw message to the registered handler for the given rail.

        Raises:
            KeyError: If no handler is registered for the rail.
            ValueError: If the handler raises a parsing error.
        """
        handler = self._handlers.get(rail)
        if handler is None:
            raise KeyError(f"No handler registered for settlement rail '{rail}'")
        return handler.handle(raw_message)

    @classmethod
    def create_default(cls) -> "SettlementHandlerRegistry":
        """Create a registry pre-loaded with all 5 default rail handlers."""
        registry = cls()
        registry.register(SettlementRail.SWIFT, SWIFTCamt054Handler())
        registry.register(SettlementRail.FEDNOW, FedNowHandler())
        registry.register(SettlementRail.RTP, RTPHandler())
        registry.register(SettlementRail.SEPA, SEPAHandler())
        registry.register(SettlementRail.BUFFER, BufferSettlementHandler())
        logger.info("SettlementHandlerRegistry initialised with all 5 default handlers.")
        return registry
