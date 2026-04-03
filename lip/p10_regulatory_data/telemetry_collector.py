"""
telemetry_collector.py — P10 TelemetryCollector.

Bridges C5 NormalizedEvent objects into the P10 anonymization pipeline.

Data flow:
  NormalizedEvent (C5) → TelemetryCollector → TelemetryBatch
                       → RegulatoryAnonymizer → SystemicRiskEngine
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List

from lip.common.constants import (
    P10_AMOUNT_BUCKET_THRESHOLDS,
    P10_AMOUNT_BUCKETS,
    P10_TIMESTAMP_BUCKET_HOURS,
)
from lip.p10_regulatory_data.telemetry_schema import CorridorStatistic, TelemetryBatch

if TYPE_CHECKING:
    from lip.c5_streaming.event_normalizer import NormalizedEvent

# ---------------------------------------------------------------------------
# Rejection code classification tables
# Hardcoded to mirror event_normalizer.py and avoid circular imports.
# Canonical source: lip/c3_repayment_engine/rejection_taxonomy.py
# ---------------------------------------------------------------------------
_BLOCK_CODES: frozenset[str] = frozenset({
    "DNOR", "CNOR",
    "RR01", "RR02", "RR03", "RR04",
    "AG01", "LEGL",
    "DISP", "DUPL", "FRAD", "FRAU",
})

_CLASS_A_CODES: frozenset[str] = frozenset({
    "AC01", "AC04", "AC06", "AC13", "BE01", "BE04",
})

_CLASS_C_CODES: frozenset[str] = frozenset({
    "AGNT", "ARDT", "NARR", "MS03", "NOAS",
})


def _classify_rejection(code: str | None) -> str | None:
    """Return failure class string for a rejection code, or None if no rejection."""
    if code is None:
        return None
    upper = code.strip().upper()
    if upper in _BLOCK_CODES:
        return "BLOCK"
    if upper in _CLASS_A_CODES:
        return "CLASS_A"
    if upper in _CLASS_C_CODES:
        return "CLASS_C"
    return "CLASS_B"


def _amount_bucket(amount: Decimal) -> str:
    """Return the P10 amount bucket label for *amount*."""
    for threshold, label in zip(P10_AMOUNT_BUCKET_THRESHOLDS, P10_AMOUNT_BUCKETS):
        if amount < threshold:
            return label
    return P10_AMOUNT_BUCKETS[-1]  # "10M+"


def _bic_country(bic: str) -> str:
    """Extract the 2-character country code from a BIC (chars 4-5, 0-indexed)."""
    if len(bic) >= 6:
        return bic[4:6].upper()
    return "XX"


def _derive_corridor(sending_bic: str, receiving_bic: str, currency: str) -> str:
    """Derive a corridor identifier from BIC country codes and currency.

    Format: ``{send_country}_{currency}-{recv_country}_{currency}``
    e.g. ``DE_EUR-FR_EUR``
    """
    send_country = _bic_country(sending_bic)
    recv_country = _bic_country(receiving_bic)
    return f"{send_country}_{currency}-{recv_country}_{currency}"


def _hash_bic(bic: str, salt: bytes) -> str:
    """SHA-256 hash the BIC with the provided salt, return hex digest."""
    h = hashlib.sha256()
    h.update(salt)
    h.update(bic.encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Internal accumulator
# ---------------------------------------------------------------------------

@dataclass
class _CorridorAccumulator:
    """Accumulates payment statistics for one (bank_hash, corridor) cell."""

    total_payments: int = 0
    failed_payments: int = 0
    failure_class_distribution: Dict[str, int] = field(default_factory=dict)
    amount_bucket_distribution: Dict[str, int] = field(default_factory=dict)
    # Simple settlement time tracking — we don't have actual settlement data in
    # NormalizedEvent; we record 0.0 as placeholder (downstream anonymizer fills)
    settlement_hours: List[float] = field(default_factory=list)

    def add(self, event: "NormalizedEvent") -> None:
        self.total_payments += 1

        bucket = _amount_bucket(event.amount)
        self.amount_bucket_distribution[bucket] = (
            self.amount_bucket_distribution.get(bucket, 0) + 1
        )

        if event.rejection_code is not None:
            self.failed_payments += 1
            cls = _classify_rejection(event.rejection_code)
            if cls is not None:
                self.failure_class_distribution[cls] = (
                    self.failure_class_distribution.get(cls, 0) + 1
                )

        # Placeholder settlement time — NormalizedEvent has no settlement field
        self.settlement_hours.append(0.0)

    def to_corridor_statistic(self, corridor: str) -> CorridorStatistic:
        failure_rate = (
            self.failed_payments / self.total_payments
            if self.total_payments > 0
            else 0.0
        )
        mean_hours = (
            sum(self.settlement_hours) / len(self.settlement_hours)
            if self.settlement_hours
            else 0.0
        )
        if self.settlement_hours:
            sorted_hours = sorted(self.settlement_hours)
            idx = int(len(sorted_hours) * 0.95)
            p95_hours = sorted_hours[min(idx, len(sorted_hours) - 1)]
        else:
            p95_hours = 0.0

        # Stress ratio: failure_rate vs naive baseline — no window data yet, use 1.0
        stress_ratio = 1.0
        stress_regime_active = False

        return CorridorStatistic(
            corridor=corridor,
            total_payments=self.total_payments,
            failed_payments=self.failed_payments,
            failure_rate=failure_rate,
            failure_class_distribution=dict(self.failure_class_distribution),
            mean_settlement_hours=mean_hours,
            p95_settlement_hours=p95_hours,
            amount_bucket_distribution=dict(self.amount_bucket_distribution),
            stress_regime_active=stress_regime_active,
            stress_ratio=stress_ratio,
        )


# ---------------------------------------------------------------------------
# TelemetryCollector
# ---------------------------------------------------------------------------

class TelemetryCollector:
    """Collect and pre-aggregate NormalizedEvents into TelemetryBatch objects.

    One TelemetryBatch is produced per distinct (bank_hash) per flush call.
    Each batch contains one CorridorStatistic per distinct corridor seen from
    that bank during the accumulation window.

    Parameters
    ----------
    salt:
        Secret bytes used for BIC hashing (SHA-256) and HMAC signing.
    bucket_hours:
        Timestamp rounding granularity (not currently applied to event
        timestamps directly — the caller supplies period_start/end on flush).
    """

    def __init__(self, salt: bytes, bucket_hours: int = P10_TIMESTAMP_BUCKET_HOURS) -> None:
        self._salt = salt
        self._bucket_hours = bucket_hours
        # { bank_hash: { corridor: _CorridorAccumulator } }
        self._accumulators: Dict[str, Dict[str, _CorridorAccumulator]] = {}
        self._events_ingested: int = 0
        self._events_filtered: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, event: "NormalizedEvent") -> bool:
        """Ingest a single NormalizedEvent.

        Returns
        -------
        bool
            ``True`` if the event was accepted; ``False`` if filtered out
            (``telemetry_eligible=False``).
        """
        if not event.telemetry_eligible:
            self._events_filtered += 1
            return False

        bank_hash = _hash_bic(event.sending_bic, self._salt)
        corridor = _derive_corridor(
            event.sending_bic, event.receiving_bic, event.currency
        )

        bank_accs = self._accumulators.setdefault(bank_hash, {})
        acc = bank_accs.setdefault(corridor, _CorridorAccumulator())
        acc.add(event)

        self._events_ingested += 1
        return True

    def flush(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TelemetryBatch]:
        """Drain accumulators into signed TelemetryBatch objects.

        Clears all accumulators after building the batches.

        Parameters
        ----------
        period_start:
            Start of the telemetry window (included in each batch).
        period_end:
            End of the telemetry window (included in each batch).

        Returns
        -------
        list[TelemetryBatch]
            One batch per distinct bank_hash. Empty list if nothing was ingested.
        """
        if not self._accumulators:
            return []

        batches: List[TelemetryBatch] = []

        for bank_hash, corridor_map in self._accumulators.items():
            corridor_stats: List[CorridorStatistic] = [
                acc.to_corridor_statistic(corridor)
                for corridor, acc in corridor_map.items()
            ]

            batch_id = str(uuid.uuid4())

            # Build a deterministic JSON payload for HMAC
            payload = json.dumps(
                {
                    "batch_id": batch_id,
                    "bank_hash": bank_hash,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "corridor_count": len(corridor_stats),
                },
                sort_keys=True,
            ).encode()

            signature = hmac.new(self._salt, payload, hashlib.sha256).hexdigest()

            batch = TelemetryBatch(
                batch_id=batch_id,
                bank_hash=bank_hash,
                period_start=period_start,
                period_end=period_end,
                corridor_statistics=corridor_stats,
                hmac_signature=signature,
            )
            batches.append(batch)

        # Clear accumulators
        self._accumulators.clear()

        return batches

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        """Number of events currently held in accumulators (not yet flushed)."""
        return sum(
            sum(acc.total_payments for acc in corridors.values())
            for corridors in self._accumulators.values()
        )

    @property
    def events_ingested(self) -> int:
        """Cumulative count of events accepted since construction."""
        return self._events_ingested

    @property
    def events_filtered(self) -> int:
        """Cumulative count of events filtered out since construction."""
        return self._events_filtered
