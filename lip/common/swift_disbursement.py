"""
swift_disbursement.py — SWIFT pacs.008 bridge disbursement message template.
GAP-06: Structured outbound message reference for bridge loan disbursements.

The ELO uses the values produced here to populate the outbound pacs.008
so that beneficiary banks and compliance teams can reconcile inbound bridge
credits against the original failed payment UETR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class BridgeDisbursementMessage:
    """Structured SWIFT pacs.008 fields for a bridge loan disbursement.

    Fields map to ISO 20022 pacs.008 as follows:
      - ``end_to_end_id``   → ``CdtTrfTxInf/PmtId/EndToEndId``
      - ``remittance_info`` → ``CdtTrfTxInf/RmtInf/Ustrd``
    """

    end_to_end_id: str      # "LIP-BRIDGE-{original_uetr}"
    remittance_info: str    # Unstructured remittance (RmtInf/Ustrd)
    original_uetr: str
    loan_id: str
    amount_usd: Decimal
    generated_at: datetime


def build_disbursement_message(
    original_uetr: str,
    loan_id: str,
    amount_usd: Decimal,
) -> BridgeDisbursementMessage:
    """Build a SWIFT pacs.008 disbursement message template for a bridge loan.

    Args:
        original_uetr: UETR of the original failed payment being bridged.
        loan_id: LIP internal loan identifier.
        amount_usd: Disbursement amount in USD.

    Returns:
        :class:`BridgeDisbursementMessage` with structured SWIFT fields ready
        for the ELO to inject into the outbound pacs.008.
    """
    return BridgeDisbursementMessage(
        end_to_end_id=f"LIP-BRIDGE-{original_uetr}",
        remittance_info=(
            f"Bridge disbursement for failed payment {original_uetr}. "
            f"Ref: LIP loan {loan_id}."
        ),
        original_uetr=original_uetr,
        loan_id=loan_id,
        amount_usd=amount_usd,
        generated_at=datetime.now(tz=timezone.utc),
    )
