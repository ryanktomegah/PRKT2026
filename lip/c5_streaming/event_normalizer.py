"""
event_normalizer.py — Multi-rail payment event normalization
C5 Spec: Normalize SWIFT/FedNow/RTP/SEPA events to canonical format

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)


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


def _safe_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal('0')


def _safe_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            pass
    return datetime.utcnow()


class EventNormalizer:
    """Normalizes payment events from all supported rails to NormalizedEvent."""

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

        return NormalizedEvent(
            uetr=ct.get('messageId', msg.get('messageId', '')),
            individual_payment_id=ct.get('endToEndId', msg.get('endToEndId', '')),
            sending_bic=msg.get('debitParty', {}).get('routingNumber', ''),
            receiving_bic=msg.get('creditParty', {}).get('routingNumber', ''),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get('timestamp') or msg.get('createdAt')),
            rail='FEDNOW',
            rejection_code=msg.get('rejectReason') or None,
            narrative=msg.get('remittanceInfo'),
            raw_source=msg,
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

        return NormalizedEvent(
            uetr=pm.get('messageId', msg.get('messageId', '')),
            individual_payment_id=pm.get('endToEndId', msg.get('endToEndId', '')),
            sending_bic=msg.get('sendingBank', ''),
            receiving_bic=msg.get('receivingBank', ''),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get('timestamp') or msg.get('createdAt')),
            rail='RTP',
            rejection_code=msg.get('rejectReason') or None,
            narrative=msg.get('narrative'),
            raw_source=msg,
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
        return handler(msg)


def normalize_event(rail: str, msg: dict) -> NormalizedEvent:
    return EventNormalizer().normalize(rail, msg)
