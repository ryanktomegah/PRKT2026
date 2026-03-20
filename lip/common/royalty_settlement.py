"""
royalty_settlement.py — Monthly BPI technology licensor royalty settlement.
GAP-05: Record and aggregate royalties for monthly collection.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass
class BPIRoyaltyRecord:
    """Individual royalty record for a repaid bridge loan."""
    uetr: str
    licensee_id: str
    royalty_usd: Decimal
    repaid_at: datetime
    loan_id: str
    deployment_phase: str = "LICENSOR"  # Phase 1=LICENSOR, Phase 2=HYBRID, Phase 3=FULL_MLO
    income_type: str = "ROYALTY"        # "ROYALTY" (Phase 1) or "LENDING_REVENUE" (Phase 2/3)


@dataclass
class MonthlySettlementReport:
    """Aggregated royalty report for a specific licensee and month."""
    licensee_id: str
    month: int
    year: int
    total_royalty_usd: Decimal
    transaction_count: int
    records: List[BPIRoyaltyRecord]
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


class BPIRoyaltySettlement:
    """Tracks and aggregates royalties for BPI collection.

    In production, this would be backed by a persistent database.
    This implementation uses an in-memory store.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[BPIRoyaltyRecord] = []

    def record_repayment(self, repayment_record: dict) -> None:
        """Extract and record royalty from a C3 repayment record."""
        try:
            uetr = repayment_record["uetr"]
            licensee_id = repayment_record.get("licensee_id", "UNKNOWN")
            royalty_usd = Decimal(str(repayment_record["platform_royalty"]))
            repaid_at_str = repayment_record["repaid_at"]
            repaid_at = datetime.fromisoformat(repaid_at_str)
            loan_id = repayment_record["loan_id"]

            record = BPIRoyaltyRecord(
                uetr=uetr,
                licensee_id=licensee_id,
                royalty_usd=royalty_usd,
                repaid_at=repaid_at,
                loan_id=loan_id,
                deployment_phase=repayment_record.get("deployment_phase", "LICENSOR"),
                income_type=repayment_record.get("income_type", "ROYALTY"),
            )

            with self._lock:
                self._records.append(record)
        except (KeyError, ValueError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).error("Failed to record royalty: %s", exc)

    def generate_monthly_settlement(
        self,
        month: int,
        year: int,
        licensee_id: Optional[str] = None
    ) -> List[MonthlySettlementReport]:
        """Aggregate royalties for the given month/year."""
        with self._lock:
            # Filter records for the target month/year
            relevant = [
                r for r in self._records
                if r.repaid_at.month == month and r.repaid_at.year == year
            ]

        # Group by licensee
        by_licensee: Dict[str, List[BPIRoyaltyRecord]] = {}
        for r in relevant:
            if licensee_id and r.licensee_id != licensee_id:
                continue
            by_licensee.setdefault(r.licensee_id, []).append(r)

        reports = []
        for lid, records in by_licensee.items():
            total = sum((r.royalty_usd for r in records), Decimal("0"))
            reports.append(MonthlySettlementReport(
                licensee_id=lid,
                month=month,
                year=year,
                total_royalty_usd=total,
                transaction_count=len(records),
                records=records
            ))

        return reports

    def clear(self) -> None:
        """Clear all records (mainly for testing)."""
        with self._lock:
            self._records.clear()
