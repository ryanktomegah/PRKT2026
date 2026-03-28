"""
revenue_metering.py — Per-processor transaction metering and revenue tracking.
P3 Platform Licensing, C8 Spec Extension.

QUANT domain: all amounts use Decimal with ROUND_HALF_UP to cents.
Invariant: processor_take_usd + bpi_net_usd == gross_fee_usd (exact).

Revenue waterfall (P3 blueprint §3.1):
  1. Gross fee collected from bridge loan
  2. Processor take = gross × platform_take_rate_pct (rounded HALF_UP to cents)
  3. BPI net = gross - processor_take (absorbs rounding residual)
  4. Performance premium = max(0, cumulative_annual_bpi_net - baseline) × premium_pct
  5. Total BPI revenue = bpi_net + performance_premium
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


@dataclass
class TransactionMeterEntry:
    """Single metered transaction."""

    tenant_id: str
    uetr: str
    gross_fee_usd: Decimal
    processor_take_usd: Decimal
    bpi_net_usd: Decimal
    metered_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class QuarterlyRevenueSummary:
    """Aggregated quarterly revenue for a processor tenant."""

    tenant_id: str
    quarter: str
    transaction_count: int
    gross_fee_usd: Decimal
    processor_take_usd: Decimal
    bpi_net_usd: Decimal
    annual_minimum_usd: Decimal
    minimum_shortfall_usd: Decimal
    performance_baseline_usd: Decimal
    above_baseline_usd: Decimal
    performance_premium_usd: Decimal
    total_bpi_revenue_usd: Decimal


class RevenueMetering:
    """Per-processor revenue tracking with penny-exact Decimal arithmetic.

    In-memory storage for Session 1. Redis persistence will be added in Sprint 5.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, List[TransactionMeterEntry]] = defaultdict(list)

    def record_transaction(
        self,
        tenant_id: str,
        uetr: str,
        gross_fee_usd: Decimal,
        platform_take_rate_pct: Decimal,
    ) -> TransactionMeterEntry:
        """Record a single metered transaction.

        QUANT invariant: processor_take + bpi_net == gross_fee (exact).
        Processor take rounded HALF_UP to cents; BPI absorbs residual.
        """
        processor_take = (gross_fee_usd * platform_take_rate_pct).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )
        bpi_net = gross_fee_usd - processor_take

        entry = TransactionMeterEntry(
            tenant_id=tenant_id,
            uetr=uetr,
            gross_fee_usd=gross_fee_usd,
            processor_take_usd=processor_take,
            bpi_net_usd=bpi_net,
        )
        self._entries[tenant_id].append(entry)
        return entry

    def compute_quarterly_summary(
        self,
        tenant_id: str,
        quarter: str,
        annual_minimum_usd: Decimal,
        performance_premium_pct: Decimal,
        performance_baseline_usd: Decimal,
    ) -> QuarterlyRevenueSummary:
        """Compute quarterly revenue summary.

        Performance premium applies only to BPI net revenue ABOVE baseline.
        """
        entries = self._entries.get(tenant_id, [])
        tx_count = len(entries)
        gross = sum((e.gross_fee_usd for e in entries), Decimal("0"))
        proc_take = sum((e.processor_take_usd for e in entries), Decimal("0"))
        bpi_net = sum((e.bpi_net_usd for e in entries), Decimal("0"))

        above_baseline = max(Decimal("0"), bpi_net - performance_baseline_usd)
        premium = (above_baseline * performance_premium_pct).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )
        total_bpi = bpi_net + premium

        # Quarterly shortfall indicator (monitoring only, not invoicing)
        shortfall = max(Decimal("0"), annual_minimum_usd - bpi_net)

        return QuarterlyRevenueSummary(
            tenant_id=tenant_id,
            quarter=quarter,
            transaction_count=tx_count,
            gross_fee_usd=gross,
            processor_take_usd=proc_take,
            bpi_net_usd=bpi_net,
            annual_minimum_usd=annual_minimum_usd,
            minimum_shortfall_usd=shortfall,
            performance_baseline_usd=performance_baseline_usd,
            above_baseline_usd=above_baseline,
            performance_premium_usd=premium,
            total_bpi_revenue_usd=total_bpi,
        )

    def check_annual_minimum_shortfall(
        self,
        tenant_id: str,
        annual_minimum_usd: Decimal,
        year: int,
    ) -> Decimal:
        """Return shortfall amount (Decimal 0 if on track).

        Shortfall = max(0, annual_minimum - cumulative_bpi_net).
        """
        entries = self._entries.get(tenant_id, [])
        bpi_net = sum((e.bpi_net_usd for e in entries), Decimal("0"))
        return max(Decimal("0"), annual_minimum_usd - bpi_net)
