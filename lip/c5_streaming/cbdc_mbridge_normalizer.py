"""
cbdc_mbridge_normalizer.py — BIS mBridge multi-CBDC PvP atomic-settlement normalizer.

Real-world context (verified April 2026):
  - mBridge: post-BIS-exit (Oct 2024), operated by 5 central banks (PBOC, HKMA,
    BoT, CBUAE, SAMA) with 31 observers. ~$55.5B settled across ~4,000
    transactions. e-CNY accounts for 95% of volume.
  - Architecture: shared mBridge Ledger (purpose-built DLT). Atomic PvP
    settlement across up to 5 currencies (CNY/HKD/THB/AED/SAR). 1-3s finality.
  - ISO 20022 native (pacs.008/pacs.002) with DLT extensions for finality and
    consensus.

Patent reference: P5 Family 5 Independent Claim 1 (heterogeneous-rail
normalisation + unified bridge-lending pipeline). The multi-leg PvP shape is a
future P9 continuation hook — code-level support, not filing.

NOVA sign-off: payments protocol modelling.
REX sign-off: regulatory disclosure of mBridge-specific failure handling.

Schema notice: BIS Innovation Hub has not published a formal production message
schema. The normalizer treats incoming messages as a documented dict shape;
swap to the official ISO 20022 mBridge profile when published.
"""
from __future__ import annotations

import logging
from typing import Optional

from lip.c5_streaming.cbdc_normalizer import normalize_cbdc_failure_code
from lip.c5_streaming.event_normalizer import (
    NormalizedEvent,
    _compute_telemetry_eligibility,
    _safe_datetime,
    _safe_decimal,
)

logger = logging.getLogger(__name__)

# Currencies seen on mBridge as of April 2026.
MBRIDGE_SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {"CNY", "HKD", "THB", "AED", "SAR"}
)


class MBridgeNormalizer:
    """Normalize mBridge atomic PvP settlement failure events to NormalizedEvent.

    A single mBridge transaction may contain up to 5 currency legs settling
    atomically (PvP — payment-versus-payment). Failures may originate in any
    leg or in the bridge consensus layer.

    The normalized event surfaces the FAILED leg as the primary NormalizedEvent;
    sister legs and bridge metadata are preserved in raw_source for downstream
    forensic / regulatory reporting.

    Selection rule for the failed leg:
      1. If msg['failed_leg_index'] is present and in range, use that leg.
      2. Else, find the first leg with status == 'FAILED'.
      3. If no failed leg can be identified, raise ValueError.
    """

    def normalize(self, msg: dict) -> NormalizedEvent:
        leg = self._select_failed_leg(msg)

        amount = _safe_decimal(leg.get("amount", "0"))
        currency = leg.get("currency", "")

        sttlm = leg.get("settlement_amount")
        original_amount = _safe_decimal(sttlm) if sttlm else None

        event = NormalizedEvent(
            uetr=msg.get("bridge_tx_id", ""),
            individual_payment_id=msg.get(
                "atomic_settlement_id", msg.get("bridge_tx_id", "")
            ),
            sending_bic=leg.get("sender_bic", leg.get("sender_wallet", "")),
            receiving_bic=leg.get("receiver_bic", leg.get("receiver_wallet", "")),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get("timestamp")),
            rail="CBDC_MBRIDGE",
            rejection_code=normalize_cbdc_failure_code(leg.get("failure_code")),
            narrative=leg.get("failure_description"),
            raw_source=msg,  # preserves all sister legs + bridge metadata
            original_payment_amount_usd=original_amount,
        )
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event

    @staticmethod
    def _select_failed_leg(msg: dict) -> dict:
        legs = msg.get("legs", [])
        if not legs:
            raise ValueError("mBridge message has no legs — invalid PvP event")

        idx: Optional[int] = msg.get("failed_leg_index")
        if idx is not None and 0 <= idx < len(legs):
            return legs[idx]

        for leg in legs:
            if str(leg.get("status", "")).upper() == "FAILED":
                return leg

        raise ValueError(
            "mBridge message has no failed leg — atomic PvP success has no "
            "bridge-lending implications and should not reach the normalizer"
        )
