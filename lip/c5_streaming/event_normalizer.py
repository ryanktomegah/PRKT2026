"""
event_normalizer.py — Multi-rail payment event normalization
C5 Spec: Normalize SWIFT/FedNow/RTP/SEPA events to canonical format

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import json as _json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path as _Path
from typing import Optional

from lip.common.block_codes import ALL_BLOCK_CODES as _BLOCK_REJECTION_CODES
from lip.common.constants import P10_TELEMETRY_MIN_AMOUNT_USD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# P10 Sprint 6 — telemetry eligibility constants
# ---------------------------------------------------------------------------
# BLOCK-class rejection codes are loaded from lip.common.block_codes (B6-01).
# That module is the single source of truth shared across Python, Rust, and Go;
# the cross-language drift test (B13-02) keeps every consumer in sync.
# lip.common.block_codes is import-side-effect-free aside from JSON load, so it
# does not reintroduce the historical event_normalizer → c3 → c2 → p5 → c5
# circular import.

# Sentinel BIC used by test/sandbox transactions across all rails.
_TEST_BIC = "XXXXXXXXXXX"

# ---------------------------------------------------------------------------
# Proprietary rejection code normalisation — FedNow / RTP → ISO 20022
# ---------------------------------------------------------------------------
# FedNow (ISO 20022-based) and RTP (proprietary) surface rejection reasons as
# free-form strings in their connector layer.  This table maps known proprietary
# strings to their canonical ISO 20022 equivalents so downstream gates (C7
# compliance hold, rejection taxonomy) operate on a uniform code space.
#
# Population guidance:
#   - Add entries when a new FedNow/RTP connector string is observed in
#     production logs.  Source: Fed's FedNow Participant Communication and
#     TCH's RTP Implementation Guide.
#   - DO NOT add entries based on inference — only confirmed mappings.
#   - Unknown codes are passed through unchanged; C7 and the taxonomy treat
#     them as unrecognised and apply the safe default (7-day maturity / no offer).
# B6-03: Loaded from shared JSON — single source of truth for Python and Go.
# Do NOT hand-maintain a parallel dict here.
_PROPRIETARY_TO_ISO20022: dict[str, str] = _json.loads(
    (_Path(__file__).resolve().parents[1] / "common" / "proprietary_iso20022_map.json")
    .read_text()
)["mapping"]


def _normalize_rejection_code(code: str | None, rail: str) -> str | None:
    """Normalise a raw rejection code string to its ISO 20022 equivalent.

    SWIFT and SEPA already surface ISO 20022 codes natively — passed through
    unchanged.  FedNow and RTP may surface proprietary strings; these are
    mapped via ``_PROPRIETARY_TO_ISO20022``.  Unrecognised codes are returned
    as-is with a warning so the downstream taxonomy treats them safely.

    Parameters
    ----------
    code:
        Raw rejection code from the connector layer (may be None).
    rail:
        Payment rail — one of SWIFT / FEDNOW / RTP / SEPA.

    Returns
    -------
    str or None
        ISO 20022 code if a mapping exists, original string otherwise, or
        None when ``code`` is absent.
    """
    if not code:
        return None
    if rail.upper() in ("SWIFT", "SEPA"):
        return code  # already ISO 20022
    upper = code.strip().upper()
    mapped = _PROPRIETARY_TO_ISO20022.get(upper)
    if mapped:
        return mapped
    # Unknown proprietary code — log and pass through so the taxonomy falls
    # back to its safe default rather than silently suppressing the signal.
    logger.warning(
        "Unknown proprietary rejection code from rail=%s code=%r — "
        "add mapping to _PROPRIETARY_TO_ISO20022 if ISO 20022 equivalent is known.",
        rail, code,
    )
    return code


@dataclass
class NormalizedEvent:
    """Canonical payment event format used across all rails."""
    uetr: str
    individual_payment_id: str
    sending_bic: str
    receiving_bic: str
    amount: Decimal
    currency: str
    timestamp: datetime
    rail: str
    rejection_code: Optional[str] = None
    narrative: Optional[str] = None
    raw_source: dict = field(default_factory=dict)
    # GAP-17: ISO 20022 interbank settlement amount in USD (IntrBkSttlmAmt).
    # Populated when the raw source carries an explicit settlement amount distinct
    # from the instructed amount (e.g. cross-currency pacs.008). None means the
    # pipeline falls back to `amount` when building the loan offer.
    original_payment_amount_usd: Optional[Decimal] = None
    # EPG-28: end-customer account identifier extracted from OrgnlTxRef.DbtrAcct
    # (IBAN or Othr.Id). When present, the pipeline uses a composite
    # (sending_bic, debtor_account) AML velocity key so each originator within
    # a correspondent bank has its own rolling window. None → falls back to BIC-only.
    debtor_account: Optional[str] = None
    # P10 Sprint 6: whether this event feeds the regulatory telemetry pipeline.
    # False for BLOCK-class rejections, sub-$1K amounts, and test/sandbox transactions.
    telemetry_eligible: bool = True


def _is_test_transaction(event: 'NormalizedEvent') -> bool:
    """Return True if the event originates from a test or sandbox source.

    Detection heuristics:
      1. UETR starts with ``TEST-`` (case-insensitive)
      2. Sending or receiving BIC equals the sentinel ``XXXXXXXXXXX``
      3. ``raw_source`` dict has a truthy ``is_test`` key
    """
    if event.uetr.upper().startswith("TEST-"):
        return True
    if event.sending_bic.upper() == _TEST_BIC or event.receiving_bic.upper() == _TEST_BIC:
        return True
    if isinstance(event.raw_source, dict) and event.raw_source.get("is_test"):
        return True
    return False


def _compute_telemetry_eligibility(event: 'NormalizedEvent') -> bool:
    """Determine whether *event* should feed the P10 hourly telemetry batch.

    Returns ``False`` (ineligible) when any of these rules fire:
      1. Rejection code belongs to the BLOCK class in the rejection taxonomy.
      2. Transaction amount is below ``P10_TELEMETRY_MIN_AMOUNT_USD`` ($1,000).
      3. Transaction is a test/sandbox event (see :func:`_is_test_transaction`).
    """
    # Rule 1: BLOCK-class rejection
    if event.rejection_code and event.rejection_code.strip().upper() in _BLOCK_REJECTION_CODES:
        return False
    # Rule 2: Sub-threshold amount
    if event.amount < P10_TELEMETRY_MIN_AMOUNT_USD:
        return False
    # Rule 3: Test / sandbox transaction
    if _is_test_transaction(event):
        return False
    return True


def _safe_decimal(value) -> Decimal:
    """Coerce ``value`` to :class:`~decimal.Decimal`, returning ``Decimal('0')`` on failure.

    Args:
        value: Numeric value to convert (int, float, str, or Decimal).

    Returns:
        Parsed :class:`~decimal.Decimal`, or ``Decimal('0')`` when ``value``
        is ``None``, non-numeric, or raises :class:`~decimal.InvalidOperation`.
    """
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal('0')


def _safe_datetime(value) -> datetime:
    """Coerce ``value`` to a :class:`~datetime.datetime`, falling back to UTC now.

    Accepts an existing :class:`~datetime.datetime` (returned as-is),
    an ISO 8601 string, or any value that can be converted to a string
    understood by :func:`~datetime.datetime.fromisoformat`.

    Args:
        value: Datetime value to parse (datetime, str, or None).

    Returns:
        Parsed :class:`~datetime.datetime`, or ``datetime.now(UTC)`` when
        ``value`` is ``None``, empty, or cannot be parsed.
    """
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            pass
    return datetime.now(tz=timezone.utc)


class EventNormalizer:
    """Normalizes payment events from all supported rails to NormalizedEvent.

    Optionally accepts a :class:`~lip.c5_streaming.cancellation_detector.CancellationDetector`
    for handling camt.056 (payment recall) and pacs.004 (payment return) messages.
    """

    def __init__(self, cancellation_detector=None) -> None:
        self._cancellation_detector = cancellation_detector

    def process_cancellation(self, message_type: str, msg: dict) -> list:
        """Process a camt.056 or pacs.004 cancellation/return message.

        Parameters
        ----------
        message_type:
            ``"CAMT056"`` or ``"PACS004"``.
        msg:
            Raw ISO 20022 message dict.

        Returns
        -------
        list
            List of :class:`~lip.c5_streaming.cancellation_detector.CancellationAlert`
            objects. Empty if no detector is configured.
        """
        if self._cancellation_detector is None:
            logger.warning("Cancellation message received but no detector configured")
            return []

        from lip.c5_streaming.cancellation_detector import normalize_camt056, normalize_pacs004

        if message_type.upper() == "CAMT056":
            event = normalize_camt056(msg)
        elif message_type.upper() == "PACS004":
            event = normalize_pacs004(msg)
        else:
            logger.warning("Unknown cancellation message type: %s", message_type)
            return []

        return self._cancellation_detector.process_cancellation(event)

    def normalize_swift(self, msg: dict) -> NormalizedEvent:
        """Parse SWIFT pacs.002 / camt.054 message."""
        grp = msg.get('GrpHdr', {})
        tx = msg.get('TxInfAndSts', {})
        sts_rsn = tx.get('StsRsnInf', {})
        orig_ref = tx.get('OrgnlTxRef', {})
        amt_block = orig_ref.get('Amt', {})
        inst_amt = amt_block.get('InstdAmt', {})

        if isinstance(inst_amt, dict):
            amount = _safe_decimal(inst_amt.get('value', inst_amt.get('Amt', '0')))
            currency = inst_amt.get('Ccy', inst_amt.get('currency', 'USD'))
        else:
            amount = _safe_decimal(inst_amt)
            currency = orig_ref.get('Ccy', 'USD')

        sending_bic = (
            msg.get('DbtrAgt', {}).get('FinInstnId', {}).get('BIC', '')
            or tx.get('DbtrAgt', {}).get('FinInstnId', {}).get('BIC', '')
        )
        receiving_bic = grp.get('InstdAgt', {}).get('FinInstnId', {}).get('BIC', '')

        rsn = sts_rsn.get('Rsn', {})
        rejection_code = rsn.get('Cd') if isinstance(rsn, dict) else rsn

        # GAP-17: Extract interbank settlement amount (IntrBkSttlmAmt in pacs.008)
        # as the authoritative USD amount the beneficiary will receive.
        sttlm = msg.get('IntrBkSttlmAmt', {})
        if isinstance(sttlm, dict):
            sttlm_val = _safe_decimal(sttlm.get('value', sttlm.get('Amt', None)))
        else:
            sttlm_val = _safe_decimal(sttlm)
        original_payment_amount_usd = sttlm_val if sttlm_val > Decimal('0') else None

        # EPG-28: extract end-customer debtor account for composite velocity key.
        # ISO 20022 pacs.002 / pacs.008: OrgnlTxRef.DbtrAcct.Id.IBAN or .Othr.Id
        dbtr_acct_id = orig_ref.get('DbtrAcct', {}).get('Id', {})
        debtor_account = (
            dbtr_acct_id.get('IBAN')
            or dbtr_acct_id.get('Othr', {}).get('Id')
        ) or None

        return NormalizedEvent(
            uetr=grp.get('MsgId', ''),
            individual_payment_id=tx.get('OrgnlEndToEndId', ''),
            sending_bic=sending_bic,
            receiving_bic=receiving_bic,
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(grp.get('CreDtTm')),
            rail='SWIFT',
            rejection_code=rejection_code or None,
            narrative=tx.get('AddtlInf'),
            raw_source=msg,
            original_payment_amount_usd=original_payment_amount_usd,
            debtor_account=debtor_account,
        )

    def normalize_fednow(self, msg: dict) -> NormalizedEvent:
        """Parse FedNow message."""
        ct = msg.get('creditTransfer', msg)
        amt_block = ct.get('amount', msg.get('amount', {}))

        if isinstance(amt_block, dict):
            amount = _safe_decimal(amt_block.get('value', '0'))
            currency = amt_block.get('currency', 'USD')
        else:
            amount = _safe_decimal(amt_block)
            currency = msg.get('currency', 'USD')

        # GAP-17: FedNow settlement amount equals instructed amount; no separate field.
        fednow_sttlm = msg.get('settlementAmount', {})
        if isinstance(fednow_sttlm, dict):
            fednow_sttlm_val = _safe_decimal(fednow_sttlm.get('value', '0'))
        else:
            fednow_sttlm_val = _safe_decimal(fednow_sttlm)
        original_payment_amount_usd = fednow_sttlm_val if fednow_sttlm_val > Decimal('0') else None

        return NormalizedEvent(
            uetr=ct.get('messageId', msg.get('messageId', '')),
            individual_payment_id=ct.get('endToEndId', msg.get('endToEndId', '')),
            sending_bic=msg.get('debitParty', {}).get('routingNumber', ''),
            receiving_bic=msg.get('creditParty', {}).get('routingNumber', ''),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get('timestamp') or msg.get('createdAt')),
            rail='FEDNOW',
            rejection_code=_normalize_rejection_code(msg.get('rejectReason'), 'FEDNOW'),
            narrative=msg.get('remittanceInfo'),
            raw_source=msg,
            original_payment_amount_usd=original_payment_amount_usd,
        )

    def normalize_rtp(self, msg: dict) -> NormalizedEvent:
        """Parse RTP message."""
        pm = msg.get('paymentMessage', msg)

        if isinstance(msg.get('amount'), dict):
            amount = _safe_decimal(msg['amount'].get('value', '0'))
            currency = msg['amount'].get('currency', 'USD')
        else:
            amount = _safe_decimal(msg.get('amount', '0'))
            currency = msg.get('currency', 'USD')

        # GAP-17: RTP settlement amount equals instructed amount; no separate field.
        rtp_sttlm = msg.get('settlementAmount', {})
        if isinstance(rtp_sttlm, dict):
            rtp_sttlm_val = _safe_decimal(rtp_sttlm.get('value', '0'))
        else:
            rtp_sttlm_val = _safe_decimal(rtp_sttlm)
        original_payment_amount_usd = rtp_sttlm_val if rtp_sttlm_val > Decimal('0') else None

        return NormalizedEvent(
            uetr=pm.get('messageId', msg.get('messageId', '')),
            individual_payment_id=pm.get('endToEndId', msg.get('endToEndId', '')),
            sending_bic=msg.get('sendingBank', ''),
            receiving_bic=msg.get('receivingBank', ''),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get('timestamp') or msg.get('createdAt')),
            rail='RTP',
            rejection_code=_normalize_rejection_code(msg.get('rejectReason'), 'RTP'),
            narrative=msg.get('narrative'),
            raw_source=msg,
            original_payment_amount_usd=original_payment_amount_usd,
        )

    def normalize_sepa(self, msg: dict) -> NormalizedEvent:
        """Parse SEPA message."""
        rpt = msg.get('FIToFIPmtStsRpt', msg)
        grp = rpt.get('GrpHdr', msg.get('GrpHdr', {}))
        tx = rpt.get('TxInfAndSts', msg.get('TxInfAndSts', {}))
        orig_ref = tx.get('OrgnlTxRef', {})
        amt_block = orig_ref.get('Amt', {})
        inst_amt = amt_block.get('InstdAmt', {})

        if isinstance(inst_amt, dict):
            amount = _safe_decimal(inst_amt.get('value', inst_amt.get('Amt', '0')))
            currency = inst_amt.get('Ccy', 'EUR')
        else:
            amount = _safe_decimal(inst_amt)
            currency = orig_ref.get('Ccy', 'EUR')

        sending_bic = (
            rpt.get('DbtrAgt', {}).get('FinInstnId', {}).get('BIC', '')
            or tx.get('DbtrAgt', {}).get('FinInstnId', {}).get('BIC', '')
        )
        receiving_bic = (
            grp.get('InstdAgt', {}).get('FinInstnId', {}).get('BIC', '')
            or rpt.get('CdtrAgt', {}).get('FinInstnId', {}).get('BIC', '')
        )

        sts_rsn = tx.get('StsRsnInf', {})
        rsn = sts_rsn.get('Rsn', {})
        rejection_code = rsn.get('Cd') if isinstance(rsn, dict) else rsn

        # GAP-17: SEPA interbank settlement amount (IntrBkSttlmAmt in pacs.008).
        sepa_sttlm = msg.get('IntrBkSttlmAmt', {})
        if isinstance(sepa_sttlm, dict):
            sepa_sttlm_val = _safe_decimal(sepa_sttlm.get('value', sepa_sttlm.get('Amt', '0')))
        else:
            sepa_sttlm_val = _safe_decimal(sepa_sttlm)
        original_payment_amount_usd = sepa_sttlm_val if sepa_sttlm_val > Decimal('0') else None

        return NormalizedEvent(
            uetr=tx.get('OrgnlEndToEndId', grp.get('MsgId', '')),
            individual_payment_id=tx.get('OrgnlEndToEndId', ''),
            sending_bic=sending_bic,
            receiving_bic=receiving_bic,
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(grp.get('CreDtTm')),
            rail='SEPA',
            rejection_code=rejection_code or None,
            narrative=tx.get('AddtlInf'),
            raw_source=msg,
            original_payment_amount_usd=original_payment_amount_usd,
        )

    def normalize(self, rail: str, msg: dict) -> NormalizedEvent:
        """Dispatch to correct normalizer based on rail string."""
        handlers = {
            'SWIFT': self.normalize_swift,
            'FEDNOW': self.normalize_fednow,
            'RTP': self.normalize_rtp,
            'SEPA': self.normalize_sepa,
        }
        handler = handlers.get(rail.upper())
        if handler is None:
            raise ValueError(f"Unknown rail: {rail}")
        event = handler(msg)
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event


def normalize_event(rail: str, msg: dict) -> NormalizedEvent:
    """Convenience wrapper — normalise a single payment event from ``rail``.

    Creates a one-shot :class:`EventNormalizer` and delegates to
    :meth:`~EventNormalizer.normalize`.  For high-throughput paths, prefer
    reusing an :class:`EventNormalizer` instance directly.

    Args:
        rail: Payment rail identifier — one of ``'SWIFT'``, ``'FEDNOW'``,
            ``'RTP'``, or ``'SEPA'`` (case-insensitive).
        msg: Raw message dict from the payment network connector.

    Returns:
        :class:`NormalizedEvent` in the canonical LIP format.

    Raises:
        ValueError: If ``rail`` is not a recognised payment rail.
    """
    return EventNormalizer().normalize(rail, msg)
