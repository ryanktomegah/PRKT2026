"""
settlement_bridge.py — Routes C3 repayment events to downstream consumers.

Replaces the no-op lambda in app.py with a bridge that fans out to:
  1. BPIRoyaltySettlement.record_repayment() — always (bank + processor mode)
  2. RevenueMetering.record_transaction() — processor mode only
  3. NAVEventEmitter.record_settlement() — processor mode only

Implements __call__ so it can be passed directly as RepaymentLoop's
repayment_callback parameter (Callable[[dict], None]).
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class SettlementCallbackBridge:
    """Fan-out bridge for C3 repayment events.

    Bank mode: only ``royalty_settlement`` is required.
    Processor mode: add ``revenue_metering``, ``nav_emitter``, and
    ``platform_take_rate_pct`` for tenant-scoped revenue tracking.
    """

    def __init__(
        self,
        royalty_settlement,
        revenue_metering=None,
        nav_emitter=None,
        platform_take_rate_pct: Optional[Decimal] = None,
    ) -> None:
        self._royalty = royalty_settlement
        self._revenue = revenue_metering
        self._nav = nav_emitter
        self._take_rate = platform_take_rate_pct

    def upgrade_to_processor_mode(
        self,
        revenue_metering,
        nav_emitter,
        platform_take_rate_pct: Decimal,
    ) -> None:
        """Upgrade a bank-mode bridge to processor mode.

        Called by app.py when processor_context is available. This avoids
        reconstructing RepaymentLoop (which takes the bridge as a callback)
        and prevents private attribute mutation from outside the class.
        """
        self._revenue = revenue_metering
        self._nav = nav_emitter
        self._take_rate = platform_take_rate_pct

    def __call__(self, repayment_record: dict) -> None:
        """Route a repayment event to all configured downstream consumers.

        Each consumer is called independently — a failure in one does not
        block the others.  Exceptions are logged but not re-raised.
        """
        # 1. BPI royalty recording (always — bank + processor mode)
        try:
            self._royalty.record_repayment(repayment_record)
        except Exception as exc:
            logger.error(
                "Royalty recording failed for uetr=%s: %s",
                repayment_record.get("uetr"),
                exc,
            )

        tenant_id = repayment_record.get("licensee_id", "")
        if not tenant_id:
            return  # Bank-originated — no processor paths

        # 2. Revenue metering (processor mode)
        if self._revenue is not None and self._take_rate is not None:
            try:
                self._revenue.record_transaction(
                    tenant_id=tenant_id,
                    uetr=repayment_record["uetr"],
                    gross_fee_usd=Decimal(repayment_record["fee"]),
                    platform_take_rate_pct=self._take_rate,
                )
            except Exception as exc:
                logger.error(
                    "Revenue metering failed for uetr=%s tenant=%s: %s",
                    repayment_record.get("uetr"),
                    tenant_id,
                    exc,
                )

        # 3. NAV settlement history (processor mode)
        if self._nav is not None:
            try:
                self._nav.record_settlement(
                    tenant_id=tenant_id,
                    amount=Decimal(repayment_record["settlement_amount"]),
                    timestamp=datetime.fromisoformat(repayment_record["repaid_at"]),
                )
            except Exception as exc:
                logger.error(
                    "NAV settlement recording failed for uetr=%s tenant=%s: %s",
                    repayment_record.get("uetr"),
                    tenant_id,
                    exc,
                )
