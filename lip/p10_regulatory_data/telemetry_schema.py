"""
telemetry_schema.py — P10 telemetry data structures.

Dataclasses (not Pydantic) for internal pipeline data. Pydantic schemas
for API boundaries live in lip/common/schemas.py (future sprint).

All structures match the P10 Blueprint Section 4.2 pre-aggregation schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class CorridorStatistic:
    """Per-corridor statistics within a single bank's hourly telemetry batch."""

    corridor: str
    total_payments: int
    failed_payments: int
    failure_rate: float
    failure_class_distribution: Dict[str, int]
    mean_settlement_hours: float
    p95_settlement_hours: float
    amount_bucket_distribution: Dict[str, int]
    stress_regime_active: bool
    stress_ratio: float


@dataclass
class TelemetryBatch:
    """Pre-aggregated telemetry from one bank, one hour.

    Arrives encrypted (AES-256-GCM) and HMAC-signed. The hmac_signature
    field is verified before any processing (CIPHER requirement).
    """

    batch_id: str
    bank_hash: str
    period_start: datetime
    period_end: datetime
    corridor_statistics: List[CorridorStatistic]
    hmac_signature: str


@dataclass
class AnonymizedCorridorResult:
    """Output of the full 3-layer anonymization pipeline.

    Consumed by the Systemic Risk Engine (future sprint) and the
    Regulatory API (future sprint).
    """

    corridor: str
    period_label: str
    total_payments: int
    failed_payments: int
    failure_rate: float
    bank_count: int
    k_anonymity_satisfied: bool
    privacy_budget_remaining: float
    noise_applied: bool
    stale: bool


@dataclass
class PrivacyBudgetStatus:
    """Snapshot of a corridor's remaining differential privacy budget."""

    corridor: str
    budget_total: float
    budget_spent: float
    budget_remaining: float
    queries_executed: int
    cycle_start: datetime
    is_exhausted: bool
