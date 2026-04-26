"""
nexus_normalizer.py — Project Nexus / Nexus Global Payments stub (PHASE-2-STUB).

Real-world status (April 2026):
  - Nexus Global Payments (NGP) incorporated 2025 in Singapore (MAS as home regulator).
  - 5 founding banks: RBI (India), BNM (Malaysia), BSP (Philippines),
    MAS (Singapore), BoT (Thailand). Indonesia joining; ECB special observer.
  - CEO appointed; Nexus Technical Operator procurement underway.
  - Onboarding pushed to mid-2027 (BSP confirmed March 2026).
  - 60-second cross-border instant payments via ISO 20022.

Schema status:
  Nexus is ISO 20022 native — no proprietary failure-code map needed; downstream
  components consume codes via the existing ExternalStatusReason1Code path.
  Real ISO 20022 specs and rulebook expected during 2026; flesh out this stub
  when NGP publishes them.

Until then this stub returns a NormalizedEvent with rail=CBDC_NEXUS so the
end-to-end pipeline can be validated against synthetic Nexus events. Phase A's
rail-aware maturity + sub-day fee floor framework applies automatically (4h
buffer in RAIL_MATURITY_HOURS).
"""
from __future__ import annotations

import logging

from lip.c5_streaming.event_normalizer import (
    NormalizedEvent,
    _compute_telemetry_eligibility,
    _safe_datetime,
    _safe_decimal,
)

logger = logging.getLogger(__name__)


class NexusNormalizer:
    """PHASE-2-STUB: minimal Nexus rail normalizer.

    Schema modelled from BIS Nexus blueprint (July 2024). When NGP publishes
    formal ISO 20022 profiles (expected during 2026), replace the field
    accessors with the real message-element XPath / JSON paths.
    """

    def normalize(self, msg: dict) -> NormalizedEvent:
        amount = _safe_decimal(msg.get("amount", "0"))
        currency = msg.get("currency", "")

        event = NormalizedEvent(
            uetr=msg.get("transaction_id", ""),
            individual_payment_id=msg.get(
                "end_to_end_id", msg.get("transaction_id", "")
            ),
            sending_bic=msg.get("sender_bic", msg.get("sender_id", "")),
            receiving_bic=msg.get("receiver_bic", msg.get("receiver_id", "")),
            amount=amount,
            currency=currency,
            timestamp=_safe_datetime(msg.get("timestamp")),
            rail="CBDC_NEXUS",
            rejection_code=msg.get("status_reason_code"),  # ISO 20022 native
            narrative=msg.get("status_reason_description"),
            raw_source=msg,
            original_payment_amount_usd=None,
        )
        event.telemetry_eligible = _compute_telemetry_eligibility(event)
        return event
