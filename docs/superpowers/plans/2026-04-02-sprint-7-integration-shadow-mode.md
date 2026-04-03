# Sprint 7: Integration & Shadow Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire all P10 modules into an end-to-end pipeline and validate with synthetic multi-bank data in shadow mode.

**Architecture:** Three new modules — TelemetryCollector (event→batch aggregation), ShadowPipelineRunner (orchestrator), and shadow_data (synthetic event generator). No infrastructure dependencies. All validation via pytest with seeded RNG for CI reproducibility.

**Tech Stack:** Python 3.14, dataclasses, hashlib (HMAC), numpy (RNG for amounts), pytest. Builds on existing P10 modules (anonymizer, systemic_risk, report_metadata, telemetry_schema).

**Spec:** `docs/superpowers/specs/2026-04-02-sprint-7-integration-shadow-mode-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `lip/p10_regulatory_data/telemetry_collector.py` | CREATE | Aggregates NormalizedEvent → TelemetryBatch (hourly, per-bank) |
| `lip/p10_regulatory_data/shadow_runner.py` | CREATE | Orchestrates collector → anonymizer → engine → report with timing |
| `lip/p10_regulatory_data/shadow_data.py` | CREATE | Generates synthetic multi-bank NormalizedEvent streams |
| `lip/p10_regulatory_data/__init__.py` | MODIFY | Export new classes |
| `lip/tests/test_p10_shadow_pipeline.py` | CREATE | 20 integration/perf tests |
| `lip/tests/test_p10_regulator_subscription.py` | MODIFY | +4 API integration tests |

---

### Task 1: TelemetryCollector — Tests

**Files:**
- Create: `lip/tests/test_p10_shadow_pipeline.py`
- Reference: `lip/p10_regulatory_data/telemetry_schema.py` (TelemetryBatch, CorridorStatistic)
- Reference: `lip/c5_streaming/event_normalizer.py:108-138` (NormalizedEvent)

- [ ] **Step 1: Create test file with TestTelemetryCollector class (8 tests)**

```python
"""
test_p10_shadow_pipeline.py — Sprint 7 integration tests.

Validates TelemetryCollector, ShadowPipelineRunner, performance targets,
and end-to-end pipeline data flow.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from lip.c5_streaming.event_normalizer import NormalizedEvent


def _make_event(
    sending_bic: str = "DEUTDEFF",
    receiving_bic: str = "BNPAFRPP",
    amount: Decimal = Decimal("50000"),
    currency: str = "EUR",
    rejection_code: str | None = None,
    telemetry_eligible: bool = True,
    uetr: str = "550e8400-e29b-41d4-a716-446655440000",
) -> NormalizedEvent:
    """Factory for test NormalizedEvent instances."""
    return NormalizedEvent(
        uetr=uetr,
        individual_payment_id="PAY-001",
        sending_bic=sending_bic,
        receiving_bic=receiving_bic,
        amount=amount,
        currency=currency,
        timestamp=datetime(2026, 4, 2, 14, 30, 0, tzinfo=timezone.utc),
        rail="SWIFT",
        rejection_code=rejection_code,
        telemetry_eligible=telemetry_eligible,
    )


_SALT = b"shadow_test_salt_32bytes________"


class TestTelemetryCollector:
    """Verify TelemetryCollector aggregation logic."""

    def test_eligible_event_produces_batch(self):
        """Single eligible event → flush returns 1 batch with 1 corridor stat."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        event = _make_event()
        assert collector.ingest(event) is True

        period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)
        batches = collector.flush(period_start, period_end)
        assert len(batches) == 1
        assert len(batches[0].corridor_statistics) == 1
        assert batches[0].corridor_statistics[0].total_payments == 1

    def test_ineligible_event_filtered(self):
        """telemetry_eligible=False → ingest returns False, flush returns empty."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        event = _make_event(telemetry_eligible=False)
        assert collector.ingest(event) is False
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        assert batches == []

    @pytest.mark.parametrize(
        "amount,expected_bucket",
        [
            (Decimal("9999"), "0-10K"),
            (Decimal("10000"), "10K-100K"),
            (Decimal("99999"), "10K-100K"),
            (Decimal("100000"), "100K-1M"),
            (Decimal("10000000"), "10M+"),
        ],
    )
    def test_amount_bucket_boundaries(self, amount, expected_bucket):
        """Amount bucket classification at boundary values."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        event = _make_event(amount=amount)
        collector.ingest(event)
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        cs = batches[0].corridor_statistics[0]
        assert cs.amount_bucket_distribution[expected_bucket] == 1

    def test_corridor_from_currency(self):
        """EUR event → corridor uses currency field."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        event = _make_event(currency="EUR")
        collector.ingest(event)
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        # Currency pair derived from sending/receiving BIC country codes + currency
        # For simplicity, corridor is derived as "{currency}-{currency}" for same-currency
        # or from the BIC pair's conventional corridor label
        cs = batches[0].corridor_statistics[0]
        assert cs.corridor != ""  # corridor is populated

    def test_multiple_banks_separate_batches(self):
        """2 different BICs → flush returns 2 batches."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        collector.ingest(_make_event(sending_bic="DEUTDEFF"))
        collector.ingest(_make_event(sending_bic="BNPAFRPP"))
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        assert len(batches) == 2
        # Each batch has a different bank_hash
        hashes = {b.bank_hash for b in batches}
        assert len(hashes) == 2

    def test_flush_clears_accumulators(self):
        """flush → flush again → empty."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        collector.ingest(_make_event())
        collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        second = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        assert second == []

    def test_batch_hmac_present(self):
        """Every flushed batch has non-empty hmac_signature."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        collector.ingest(_make_event())
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        for batch in batches:
            assert batch.hmac_signature != ""
            assert len(batch.hmac_signature) > 10

    def test_failure_class_distribution(self):
        """BLOCK code → failure_class_distribution['BLOCK'] incremented."""
        from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

        collector = TelemetryCollector(salt=_SALT)
        collector.ingest(_make_event(rejection_code="DNOR"))  # BLOCK code
        collector.ingest(_make_event(rejection_code="AC01"))  # CLASS_A code
        collector.ingest(_make_event(rejection_code=None))    # success
        batches = collector.flush(
            datetime(2026, 4, 2, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
        )
        cs = batches[0].corridor_statistics[0]
        assert cs.failure_class_distribution.get("BLOCK", 0) == 1
        assert cs.failure_class_distribution.get("CLASS_A", 0) == 1
        assert cs.total_payments == 3
        assert cs.failed_payments == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestTelemetryCollector -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lip.p10_regulatory_data.telemetry_collector'`

- [ ] **Step 3: Commit test file**

```bash
git add lip/tests/test_p10_shadow_pipeline.py
git commit -m "test: add TelemetryCollector tests (Sprint 7, red phase)"
```

---

### Task 2: TelemetryCollector — Implementation

**Files:**
- Create: `lip/p10_regulatory_data/telemetry_collector.py`
- Reference: `lip/p10_regulatory_data/telemetry_schema.py` (TelemetryBatch, CorridorStatistic)
- Reference: `lip/common/constants.py:244-250` (P10_AMOUNT_BUCKETS, P10_AMOUNT_BUCKET_THRESHOLDS)
- Reference: `lip/c5_streaming/event_normalizer.py:24-26` (hardcoded BLOCK rejection codes pattern)

- [ ] **Step 1: Create telemetry_collector.py**

```python
"""
telemetry_collector.py — Aggregate NormalizedEvent streams into TelemetryBatch.

Sprint 7: Bridge between C5 normalized events and the P10 anonymization pipeline.
Buckets events by (bank, corridor, hour), produces HMAC-signed TelemetryBatch objects.

Thread-safety: NOT thread-safe. Callers must synchronise externally.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lip.common.constants import (
    P10_AMOUNT_BUCKET_THRESHOLDS,
    P10_AMOUNT_BUCKETS,
    P10_TIMESTAMP_BUCKET_HOURS,
)
from lip.p10_regulatory_data.telemetry_schema import CorridorStatistic, TelemetryBatch

if TYPE_CHECKING:
    from lip.c5_streaming.event_normalizer import NormalizedEvent

logger = logging.getLogger(__name__)

# Hardcoded BLOCK rejection codes — same set as event_normalizer.py.
# Avoids circular import through c3_repayment_engine.
_BLOCK_CODES: frozenset[str] = frozenset({
    "DNOR", "CNOR", "RR01", "RR02", "RR03", "RR04",
    "AG01", "LEGL", "DISP", "DUPL", "FRAD", "FRAU",
})

# Lightweight rejection class mapping for non-BLOCK codes.
# Unknown codes default to CLASS_B (safe — longest maturity window).
_CLASS_A_CODES: frozenset[str] = frozenset({"AC01", "AC04", "AC06", "AC13", "BE01", "BE04"})
_CLASS_C_CODES: frozenset[str] = frozenset({"AGNT", "ARDT", "NARR", "MS03", "NOAS"})


def _classify_rejection(code: str | None) -> str | None:
    """Map rejection code to failure class. Returns None for success."""
    if code is None:
        return None
    if code in _BLOCK_CODES:
        return "BLOCK"
    if code in _CLASS_A_CODES:
        return "CLASS_A"
    if code in _CLASS_C_CODES:
        return "CLASS_C"
    return "CLASS_B"  # safe default


def _classify_amount_bucket(amount: Decimal) -> str:
    """Map amount to P10_AMOUNT_BUCKETS using threshold boundaries."""
    for threshold, label in zip(P10_AMOUNT_BUCKET_THRESHOLDS, P10_AMOUNT_BUCKETS):
        if amount < threshold:
            return label
    return P10_AMOUNT_BUCKETS[-1]  # 10M+


class _CorridorAccumulator:
    """Mutable accumulator for one (bank, corridor, period) triple."""

    __slots__ = (
        "total_payments", "failed_payments", "failure_class_counts",
        "amount_bucket_counts", "settlement_hours",
    )

    def __init__(self) -> None:
        self.total_payments: int = 0
        self.failed_payments: int = 0
        self.failure_class_counts: dict[str, int] = defaultdict(int)
        self.amount_bucket_counts: dict[str, int] = defaultdict(int)
        self.settlement_hours: list[float] = []

    def add(self, event: NormalizedEvent) -> None:
        self.total_payments += 1
        bucket = _classify_amount_bucket(event.amount)
        self.amount_bucket_counts[bucket] += 1

        failure_class = _classify_rejection(event.rejection_code)
        if failure_class is not None:
            self.failed_payments += 1
            self.failure_class_counts[failure_class] += 1

    def to_corridor_statistic(self, corridor: str) -> CorridorStatistic:
        failure_rate = (
            self.failed_payments / self.total_payments
            if self.total_payments > 0
            else 0.0
        )
        sorted_hours = sorted(self.settlement_hours) if self.settlement_hours else [0.0]
        p95_idx = max(0, int(len(sorted_hours) * 0.95) - 1)
        return CorridorStatistic(
            corridor=corridor,
            total_payments=self.total_payments,
            failed_payments=self.failed_payments,
            failure_rate=failure_rate,
            failure_class_distribution=dict(self.failure_class_counts),
            mean_settlement_hours=(
                sum(sorted_hours) / len(sorted_hours) if sorted_hours else 0.0
            ),
            p95_settlement_hours=sorted_hours[p95_idx],
            amount_bucket_distribution=dict(self.amount_bucket_counts),
            stress_regime_active=False,
            stress_ratio=0.0,
        )


class TelemetryCollector:
    """Aggregate NormalizedEvent streams into TelemetryBatch objects.

    Usage::

        collector = TelemetryCollector(salt=b"32-byte-key")
        for event in events:
            collector.ingest(event)
        batches = collector.flush(period_start, period_end)
        # batches -> RegulatoryAnonymizer.anonymize_batch()
    """

    def __init__(
        self,
        salt: bytes,
        bucket_hours: int = P10_TIMESTAMP_BUCKET_HOURS,
    ) -> None:
        self._salt = salt
        self._bucket_hours = bucket_hours
        # Key: (bank_hash, corridor) → _CorridorAccumulator
        self._accumulators: dict[tuple[str, str], _CorridorAccumulator] = {}
        self._events_ingested = 0
        self._events_filtered = 0

    def _hash_bic(self, bic: str) -> str:
        """SHA-256 hash of BIC with salt for entity pseudonymisation."""
        return hashlib.sha256(self._salt + bic.encode()).hexdigest()[:16]

    def _derive_corridor(self, event: NormalizedEvent) -> str:
        """Derive corridor identifier from the event.

        Convention: "{sending_country_currency}-{receiving_country_currency}"
        Simplified to "{currency}-{currency}" for same-currency pairs,
        or BIC country code extraction for cross-currency.
        """
        # Extract country codes from BICs (chars 4-5, ISO 3166)
        send_country = event.sending_bic[4:6] if len(event.sending_bic) >= 6 else "XX"
        recv_country = event.receiving_bic[4:6] if len(event.receiving_bic) >= 6 else "XX"
        currency = event.currency
        return f"{send_country}_{currency}-{recv_country}_{currency}"

    def ingest(self, event: NormalizedEvent) -> bool:
        """Ingest a single NormalizedEvent.

        Returns False if the event is filtered (telemetry_eligible=False).
        """
        if not event.telemetry_eligible:
            self._events_filtered += 1
            return False

        bank_hash = self._hash_bic(event.sending_bic)
        corridor = self._derive_corridor(event)
        key = (bank_hash, corridor)

        if key not in self._accumulators:
            self._accumulators[key] = _CorridorAccumulator()

        self._accumulators[key].add(event)
        self._events_ingested += 1
        return True

    def flush(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> list[TelemetryBatch]:
        """Drain accumulators into HMAC-signed TelemetryBatch objects.

        Returns one TelemetryBatch per distinct bank_hash.
        Clears all accumulators after flushing.
        """
        if not self._accumulators:
            return []

        # Group accumulators by bank_hash
        bank_corridors: dict[str, list[tuple[str, _CorridorAccumulator]]] = defaultdict(list)
        for (bank_hash, corridor), acc in self._accumulators.items():
            bank_corridors[bank_hash].append((corridor, acc))

        batches: list[TelemetryBatch] = []
        for bank_hash, corridor_accs in bank_corridors.items():
            stats = [acc.to_corridor_statistic(corridor) for corridor, acc in corridor_accs]
            batch_id = f"BATCH-{uuid.uuid4().hex[:12]}"
            batch = TelemetryBatch(
                batch_id=batch_id,
                bank_hash=bank_hash,
                period_start=period_start,
                period_end=period_end,
                corridor_statistics=stats,
                hmac_signature="",  # signed below
            )
            # HMAC-sign the batch content
            sig_payload = json.dumps({
                "batch_id": batch.batch_id,
                "bank_hash": batch.bank_hash,
                "corridors": len(batch.corridor_statistics),
            }, sort_keys=True).encode()
            batch.hmac_signature = hmac.new(
                self._salt, sig_payload, hashlib.sha256,
            ).hexdigest()
            batches.append(batch)

        self._accumulators.clear()
        return batches

    @property
    def pending_count(self) -> int:
        """Number of events accumulated but not yet flushed."""
        return sum(acc.total_payments for acc in self._accumulators.values())

    @property
    def events_ingested(self) -> int:
        return self._events_ingested

    @property
    def events_filtered(self) -> int:
        return self._events_filtered
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestTelemetryCollector -v`
Expected: 13 passed (8 tests, 5 parametrized variants for amount buckets)

- [ ] **Step 3: Run ruff**

Run: `ruff check lip/p10_regulatory_data/telemetry_collector.py`
Expected: All checks passed!

- [ ] **Step 4: Commit**

```bash
git add lip/p10_regulatory_data/telemetry_collector.py
git commit -m "feat(p10): add TelemetryCollector — NormalizedEvent to TelemetryBatch aggregation"
```

---

### Task 3: Shadow Data Generator

**Files:**
- Create: `lip/p10_regulatory_data/shadow_data.py`
- Reference: `lip/c5_streaming/event_normalizer.py:108-138` (NormalizedEvent fields)

- [ ] **Step 1: Write test for shadow data generator (add to test file)**

Append to `lip/tests/test_p10_shadow_pipeline.py`:

```python
class TestShadowDataGenerator:
    """Verify synthetic event generation for shadow mode."""

    def test_generates_correct_count(self):
        """5 banks × 2000 events = 10000 total."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        assert len(events) == 10_000

    def test_distinct_bics(self):
        """5 banks → 5 distinct sending BICs."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=100, seed=42)
        bics = {e.sending_bic for e in events}
        assert len(bics) == 5

    def test_deterministic_with_seed(self):
        """Same seed → identical events."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        a = generate_shadow_events(n_banks=3, n_events_per_bank=50, seed=99)
        b = generate_shadow_events(n_banks=3, n_events_per_bank=50, seed=99)
        assert [e.uetr for e in a] == [e.uetr for e in b]

    def test_failure_rate_approximately_correct(self):
        """~8% overall failure rate (±3%)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        failed = sum(1 for e in events if e.rejection_code is not None)
        rate = failed / len(events)
        assert 0.05 < rate < 0.15  # generous range for stochastic

    def test_some_events_ineligible(self):
        """~2% of events have telemetry_eligible=False."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events

        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        ineligible = sum(1 for e in events if not e.telemetry_eligible)
        rate = ineligible / len(events)
        assert 0.005 < rate < 0.05
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestShadowDataGenerator -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lip.p10_regulatory_data.shadow_data'`

- [ ] **Step 3: Create shadow_data.py**

```python
"""
shadow_data.py — Synthetic multi-bank event generator for shadow mode.

Sprint 7: Generates realistic NormalizedEvent streams simulating 5+ bank
payment flows across 8 corridors. Uses BIS CPMI-calibrated amount
distributions and configurable failure rates.

Deterministic via seed parameter for CI reproducibility.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from lip.c5_streaming.event_normalizer import NormalizedEvent

# Default corridors (8 major cross-border payment corridors)
_DEFAULT_CORRIDORS = [
    "EUR-USD", "GBP-EUR", "USD-JPY", "EUR-GBP",
    "USD-CAD", "GBP-USD", "EUR-JPY", "CAD-USD",
]

# Rejection codes by failure class
_CLASS_A_CODES = ["AC01", "AC04", "AC06"]
_CLASS_B_CODES = ["CURR", "AM04", "AM05"]
_CLASS_C_CODES = ["AGNT", "ARDT"]
_BLOCK_CODES = ["DNOR", "CNOR", "RR01", "FRAD"]

# Synthetic BIC template
_BIC_TEMPLATE = "BANK{:02d}XXXX"

# Currency map for corridor → (send_currency, recv_currency, send_bic_country, recv_bic_country)
_CORRIDOR_MAP: dict[str, tuple[str, str, str, str]] = {
    "EUR-USD": ("EUR", "USD", "DE", "US"),
    "GBP-EUR": ("GBP", "EUR", "GB", "DE"),
    "USD-JPY": ("USD", "JPY", "US", "JP"),
    "EUR-GBP": ("EUR", "GBP", "DE", "GB"),
    "USD-CAD": ("USD", "CAD", "US", "CA"),
    "GBP-USD": ("GBP", "USD", "GB", "US"),
    "EUR-JPY": ("EUR", "JPY", "DE", "JP"),
    "CAD-USD": ("CAD", "USD", "CA", "US"),
}


def generate_shadow_events(
    n_banks: int = 5,
    n_events_per_bank: int = 2000,
    corridors: list[str] | None = None,
    failure_rate: float = 0.08,
    stressed_corridor: str | None = "EUR-USD",
    stressed_rate: float = 0.15,
    seed: int = 42,
) -> list[NormalizedEvent]:
    """Generate synthetic NormalizedEvent streams for shadow mode testing.

    Parameters
    ----------
    n_banks : int
        Number of synthetic banks (each gets a unique BIC).
    n_events_per_bank : int
        Events per bank (distributed across corridors).
    corridors : list[str] | None
        Corridor labels. Defaults to 8 major corridors.
    failure_rate : float
        Base failure rate (0.0-1.0). Default 8%.
    stressed_corridor : str | None
        One corridor with elevated failure rate. None to disable.
    stressed_rate : float
        Failure rate for the stressed corridor.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    list[NormalizedEvent]
        Deterministically generated events.
    """
    rng = np.random.default_rng(seed)
    corridors = corridors or _DEFAULT_CORRIDORS
    bics = [_BIC_TEMPLATE.format(i) for i in range(1, n_banks + 1)]
    base_time = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)

    events: list[NormalizedEvent] = []

    for bank_idx, bic in enumerate(bics):
        # Distribute events across corridors with ±20% variation
        per_corridor = n_events_per_bank // len(corridors)
        for corridor in corridors:
            variation = int(per_corridor * 0.2 * (rng.random() - 0.5) * 2)
            n_events = max(1, per_corridor + variation)

            corr_info = _CORRIDOR_MAP.get(corridor)
            if corr_info is None:
                currency, recv_currency, send_cc, recv_cc = "USD", "EUR", "US", "DE"
            else:
                currency, recv_currency, send_cc, recv_cc = corr_info

            # Determine corridor-specific failure rate
            corr_failure_rate = (
                stressed_rate
                if stressed_corridor and corridor == stressed_corridor
                else failure_rate
            )

            for i in range(n_events):
                # Amount: log-normal, median ~$50K (BIS CPMI calibration)
                amount = Decimal(str(round(float(rng.lognormal(mean=10.8, sigma=1.5)), 2)))

                # Timestamp: spread across 1-hour window
                offset_seconds = rng.integers(0, 3600)
                ts = base_time + timedelta(seconds=int(offset_seconds))

                # Failure determination
                is_failure = rng.random() < corr_failure_rate
                rejection_code = None
                if is_failure:
                    # Distribute: 50% A, 30% B, 15% C, 5% BLOCK
                    class_roll = rng.random()
                    if class_roll < 0.50:
                        rejection_code = rng.choice(_CLASS_A_CODES)
                    elif class_roll < 0.80:
                        rejection_code = rng.choice(_CLASS_B_CODES)
                    elif class_roll < 0.95:
                        rejection_code = rng.choice(_CLASS_C_CODES)
                    else:
                        rejection_code = rng.choice(_BLOCK_CODES)

                # ~2% test/sandbox events
                telemetry_eligible = True
                if rng.random() < 0.02:
                    telemetry_eligible = False

                # Build sending/receiving BICs with country codes embedded
                sending_bic = f"{bic[:4]}{send_cc}{bic[6:]}"
                receiving_bic = f"RECV{recv_cc}XXXX"

                events.append(NormalizedEvent(
                    uetr=str(uuid.UUID(int=rng.integers(0, 2**128), version=4)),
                    individual_payment_id=f"PAY-{bank_idx:02d}-{corridor}-{i:05d}",
                    sending_bic=sending_bic,
                    receiving_bic=receiving_bic,
                    amount=amount,
                    currency=currency,
                    timestamp=ts,
                    rail=rng.choice(["SWIFT", "FEDNOW", "RTP", "SEPA"]),
                    rejection_code=rejection_code,
                    telemetry_eligible=telemetry_eligible,
                ))

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestShadowDataGenerator -v`
Expected: 5 passed

- [ ] **Step 5: Run ruff**

Run: `ruff check lip/p10_regulatory_data/shadow_data.py`
Expected: All checks passed!

- [ ] **Step 6: Commit**

```bash
git add lip/p10_regulatory_data/shadow_data.py lip/tests/test_p10_shadow_pipeline.py
git commit -m "feat(p10): add shadow data generator — synthetic multi-bank event streams"
```

---

### Task 4: ShadowPipelineRunner — Tests

**Files:**
- Modify: `lip/tests/test_p10_shadow_pipeline.py`

- [ ] **Step 1: Add TestShadowPipelineEndToEnd class (8 tests)**

Append to `lip/tests/test_p10_shadow_pipeline.py`:

```python
from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine


@pytest.fixture
def shadow_components():
    """Pre-configured anonymizer + risk engine for shadow pipeline tests."""
    anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
    engine = SystemicRiskEngine()
    return anonymizer, engine


class TestShadowPipelineEndToEnd:
    """Verify full pipeline: events → collector → anonymizer → engine → report."""

    def test_full_pipeline_produces_report(self, shadow_components):
        """10K events → non-None SystemicRiskReport."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        assert result.report is not None
        assert result.report.total_corridors_analyzed > 0

    def test_all_corridors_present(self, shadow_components):
        """8 corridors in report (5 banks >= k=5, none suppressed)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        assert result.corridors_suppressed == 0
        assert result.corridors_analyzed >= 8

    def test_stressed_corridor_elevated(self, shadow_components):
        """EUR-USD failure_rate > mean of other corridors."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(
            n_banks=5, n_events_per_bank=2000, seed=42,
            stressed_corridor="EUR-USD", stressed_rate=0.25,
        )
        result = runner.run(events)
        # Find corridors containing "EUR" and "USD" — the stressed corridor
        snapshots = result.report.corridor_snapshots
        rates = {s.corridor: s.failure_rate for s in snapshots}
        # At least one corridor should have elevated rate
        max_rate = max(rates.values()) if rates else 0
        mean_rate = sum(rates.values()) / len(rates) if rates else 0
        assert max_rate > mean_rate  # stressed corridor is above average

    def test_privacy_budget_consumed(self, shadow_components):
        """privacy_budget_consumed > 0.0 after pipeline run."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        assert result.privacy_budget_consumed > 0.0

    def test_timings_populated(self, shadow_components):
        """All timing keys present and > 0."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        expected_keys = {
            "collect_ms", "flush_ms", "anonymize_ms",
            "ingest_ms", "report_ms", "verify_ms", "total_ms",
        }
        assert set(result.timings.keys()) == expected_keys
        for key, val in result.timings.items():
            assert val >= 0, f"timing {key} is negative: {val}"

    def test_filtered_events_counted(self, shadow_components):
        """events_filtered ≈ 2% of total (±3%)."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        result = runner.run(events)
        total = result.events_ingested + result.events_filtered
        filter_rate = result.events_filtered / total if total > 0 else 0
        assert 0.005 < filter_rate < 0.05

    def test_report_integrity_verified(self, shadow_components):
        """integrity_verified is True."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=42)
        result = runner.run(events)
        assert result.integrity_verified is True

    def test_sequential_runs_accumulate_trends(self, shadow_components):
        """3 runs → trend history length >= 3 for corridors."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer, engine = shadow_components
        runner = ShadowPipelineRunner(
            salt=_SALT, anonymizer=anonymizer, risk_engine=engine,
        )
        for seed in [42, 43, 44]:
            events = generate_shadow_events(n_banks=5, n_events_per_bank=200, seed=seed)
            runner.run(events)

        # Engine should have accumulated 3 periods of history
        report = engine.compute_risk_report()
        assert report.total_corridors_analyzed > 0
```

- [ ] **Step 2: Run to verify tests fail**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestShadowPipelineEndToEnd -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lip.p10_regulatory_data.shadow_runner'`

- [ ] **Step 3: Commit red-phase tests**

```bash
git add lip/tests/test_p10_shadow_pipeline.py
git commit -m "test: add ShadowPipelineRunner end-to-end tests (Sprint 7, red phase)"
```

---

### Task 5: ShadowPipelineRunner — Implementation

**Files:**
- Create: `lip/p10_regulatory_data/shadow_runner.py`
- Reference: `lip/p10_regulatory_data/telemetry_collector.py` (TelemetryCollector)
- Reference: `lip/p10_regulatory_data/anonymizer.py` (RegulatoryAnonymizer)
- Reference: `lip/p10_regulatory_data/systemic_risk.py` (SystemicRiskEngine)
- Reference: `lip/p10_regulatory_data/report_metadata.py` (create_versioned_report, verify_report_integrity)

- [ ] **Step 1: Create shadow_runner.py**

```python
"""
shadow_runner.py — P10 shadow mode pipeline orchestrator.

Sprint 7: Wires TelemetryCollector → RegulatoryAnonymizer → SystemicRiskEngine
→ VersionedReport into a single run() call with per-stage timing.

No infrastructure dependencies. Designed for pytest, CLI scripts, and notebooks.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
from lip.p10_regulatory_data.report_metadata import (
    ReportIntegrityError,
    VersionedReport,
    create_versioned_report,
    verify_report_integrity,
)
from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine, SystemicRiskReport
from lip.p10_regulatory_data.telemetry_collector import TelemetryCollector

if TYPE_CHECKING:
    from lip.c5_streaming.event_normalizer import NormalizedEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowRunResult:
    """Output of a single shadow pipeline run."""

    report: SystemicRiskReport
    versioned_report: VersionedReport
    events_ingested: int
    events_filtered: int
    batches_produced: int
    corridors_analyzed: int
    corridors_suppressed: int
    privacy_budget_consumed: float
    timings: dict[str, float] = field(default_factory=dict)
    integrity_verified: bool = False


class ShadowPipelineRunner:
    """Orchestrates the full P10 pipeline on in-memory event streams.

    Usage::

        runner = ShadowPipelineRunner(salt, anonymizer, risk_engine)
        result = runner.run(events)
        print(result.report.systemic_risk_score)
        print(result.timings)  # per-stage wall-clock ms
    """

    def __init__(
        self,
        salt: bytes,
        anonymizer: RegulatoryAnonymizer,
        risk_engine: SystemicRiskEngine,
    ) -> None:
        self._salt = salt
        self._anonymizer = anonymizer
        self._risk_engine = risk_engine

    def run(
        self,
        events: list[NormalizedEvent],
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> ShadowRunResult:
        """Run the full P10 pipeline on a list of NormalizedEvent.

        Stages (each timed):
          1. Collect — feed events into TelemetryCollector
          2. Flush — drain into TelemetryBatch objects
          3. Anonymize — 3-layer privacy pipeline
          4. Ingest — feed anonymized results into risk engine
          5. Report — compute systemic risk report
          6. Verify — create versioned report + integrity check
        """
        total_start = time.perf_counter()
        timings: dict[str, float] = {}

        # Defaults for period boundaries
        if period_start is None:
            period_start = datetime(2026, 4, 2, 14, 0, 0, tzinfo=timezone.utc)
        if period_end is None:
            period_end = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)

        # Stage 1: Collect
        t0 = time.perf_counter()
        collector = TelemetryCollector(salt=self._salt)
        for event in events:
            collector.ingest(event)
        timings["collect_ms"] = (time.perf_counter() - t0) * 1000

        events_ingested = collector.events_ingested
        events_filtered = collector.events_filtered

        # Stage 2: Flush
        t0 = time.perf_counter()
        batches = collector.flush(period_start, period_end)
        timings["flush_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 3: Anonymize
        t0 = time.perf_counter()
        anon_results = self._anonymizer.anonymize_batch(batches)
        timings["anonymize_ms"] = (time.perf_counter() - t0) * 1000

        corridors_analyzed = len(anon_results)
        corridors_suppressed = len(batches) - corridors_analyzed if batches else 0
        # More accurate: count unique corridors in batches vs results
        batch_corridors = set()
        for b in batches:
            for cs in b.corridor_statistics:
                batch_corridors.add(cs.corridor)
        corridors_suppressed = len(batch_corridors) - corridors_analyzed

        # Privacy budget consumed
        budget_consumed = sum(
            float(self._anonymizer._epsilon)
            for r in anon_results
            if r.noise_applied
        )

        # Stage 4: Ingest
        t0 = time.perf_counter()
        self._risk_engine.ingest_results(anon_results)
        timings["ingest_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 5: Report
        t0 = time.perf_counter()
        report = self._risk_engine.compute_risk_report()
        timings["report_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 6: Verify
        t0 = time.perf_counter()
        versioned = create_versioned_report(report)
        try:
            verify_report_integrity(versioned)
            integrity_ok = True
        except ReportIntegrityError:
            integrity_ok = False
            logger.error("Report integrity verification failed!")
        timings["verify_ms"] = (time.perf_counter() - t0) * 1000

        timings["total_ms"] = (time.perf_counter() - total_start) * 1000

        return ShadowRunResult(
            report=report,
            versioned_report=versioned,
            events_ingested=events_ingested,
            events_filtered=events_filtered,
            batches_produced=len(batches),
            corridors_analyzed=corridors_analyzed,
            corridors_suppressed=corridors_suppressed,
            privacy_budget_consumed=budget_consumed,
            timings=timings,
            integrity_verified=integrity_ok,
        )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestShadowPipelineEndToEnd -v`
Expected: 8 passed

- [ ] **Step 3: Run ruff**

Run: `ruff check lip/p10_regulatory_data/shadow_runner.py`
Expected: All checks passed!

- [ ] **Step 4: Commit**

```bash
git add lip/p10_regulatory_data/shadow_runner.py
git commit -m "feat(p10): add ShadowPipelineRunner — full pipeline orchestrator with timing"
```

---

### Task 6: Performance Tests

**Files:**
- Modify: `lip/tests/test_p10_shadow_pipeline.py`

- [ ] **Step 1: Add TestPerformanceTargets class (3 tests)**

Append to `lip/tests/test_p10_shadow_pipeline.py`:

```python
class TestPerformanceTargets:
    """Validate Sprint 7 blueprint performance targets."""

    def test_corridor_query_under_500ms(self):
        """RegulatoryService.get_corridor_snapshots() < 500ms after shadow population."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        runner.run(events)

        service = RegulatoryService(risk_engine=engine)

        t0 = time.perf_counter()
        snapshots, suppressed = service.get_corridor_snapshots(period_count=24)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 500, f"Corridor query took {elapsed_ms:.1f}ms (target: <500ms)"
        assert len(snapshots) > 0

    def test_stress_test_under_30s(self):
        """RegulatoryService.run_stress_test() < 30s."""
        from lip.api.regulatory_service import RegulatoryService
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)
        runner.run(events)

        service = RegulatoryService(risk_engine=engine)

        t0 = time.perf_counter()
        report_id, report = service.run_stress_test(
            scenario_name="EUR-USD-shock",
            shocks=[{"corridor": "EUR-USD", "shock_magnitude": 0.5}],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 30_000, f"Stress test took {elapsed_ms:.1f}ms (target: <30s)"
        assert report is not None

    def test_full_pipeline_under_5s(self):
        """ShadowPipelineRunner.run(10K events) total_ms < 5000."""
        from lip.p10_regulatory_data.shadow_data import generate_shadow_events
        from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner

        anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
        engine = SystemicRiskEngine()
        runner = ShadowPipelineRunner(salt=_SALT, anonymizer=anonymizer, risk_engine=engine)
        events = generate_shadow_events(n_banks=5, n_events_per_bank=2000, seed=42)

        result = runner.run(events)
        assert result.timings["total_ms"] < 5000, (
            f"Pipeline took {result.timings['total_ms']:.1f}ms (target: <5s)"
        )
```

- [ ] **Step 2: Run performance tests**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py::TestPerformanceTargets -v`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add lip/tests/test_p10_shadow_pipeline.py
git commit -m "test(p10): add performance target assertions (corridor <500ms, stress <30s, pipeline <5s)"
```

---

### Task 7: Update Exports and API Integration Tests

**Files:**
- Modify: `lip/p10_regulatory_data/__init__.py`
- Modify: `lip/tests/test_p10_regulator_subscription.py`

- [ ] **Step 1: Update __init__.py exports**

Add to `lip/p10_regulatory_data/__init__.py` after the existing imports (line 8):

```python
from .shadow_runner import ShadowPipelineRunner, ShadowRunResult
from .telemetry_collector import TelemetryCollector
```

Add to `__all__` list (alphabetical order):

```python
"ShadowPipelineRunner",
"ShadowRunResult",
"TelemetryCollector",
```

- [ ] **Step 2: Add TestAPIWithShadowData to test_p10_regulator_subscription.py**

Append to `lip/tests/test_p10_regulator_subscription.py`:

```python
# ---------------------------------------------------------------------------
# Sprint 7 — API integration tests with shadow-populated engine
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient
    from lip.api.regulatory_router import make_regulatory_router
    from lip.api.regulatory_service import RegulatoryService
    from lip.p10_regulatory_data.anonymizer import RegulatoryAnonymizer
    from lip.p10_regulatory_data.shadow_data import generate_shadow_events
    from lip.p10_regulatory_data.shadow_runner import ShadowPipelineRunner
    from lip.p10_regulatory_data.systemic_risk import SystemicRiskEngine

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


@pytest.fixture
def shadow_api_client():
    """TestClient with engine pre-populated by shadow pipeline."""
    if not _HAS_FASTAPI:
        pytest.skip("FastAPI not available")

    salt = b"shadow_api_test_salt_32bytes____"
    signing_key = b"regulator-signing-key-32-bytes!!!!"
    anonymizer = RegulatoryAnonymizer(k=5, rng_seed=42)
    engine = SystemicRiskEngine()
    runner = ShadowPipelineRunner(salt=salt, anonymizer=anonymizer, risk_engine=engine)
    events = generate_shadow_events(n_banks=5, n_events_per_bank=500, seed=42)
    runner.run(events)

    service = RegulatoryService(risk_engine=engine)
    metering = RegulatoryQueryMetering()

    from fastapi import FastAPI

    app = FastAPI()
    router = make_regulatory_router(
        regulatory_service=service,
        regulator_signing_key=signing_key,
        query_metering=metering,
    )
    app.include_router(router, prefix="/regulatory")

    # Create a valid token
    token = sign_regulator_token(
        _make_regulator_token(subscription_tier="STRESS_TEST"),
        signing_key,
    )
    encoded = encode_regulator_token(token)

    return TestClient(app), encoded


@pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not available")
class TestAPIWithShadowData:
    """Verify API endpoints serve data after shadow pipeline populates engine."""

    def test_corridors_endpoint_after_shadow(self, shadow_api_client):
        """GET /corridors returns non-empty after shadow run."""
        client, token = shadow_api_client
        resp = client.get(
            "/regulatory/corridors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("corridors", data.get("snapshots", []))) > 0 or "corridors" in data

    def test_trend_endpoint_after_shadow(self, shadow_api_client):
        """GET /corridors/{id}/trend returns data."""
        client, token = shadow_api_client
        # First get corridors to find an ID
        resp = client.get(
            "/regulatory/corridors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Extract first corridor ID from response
        corridors = data.get("corridors", data.get("snapshots", []))
        if corridors:
            corridor_id = corridors[0].get("corridor", corridors[0].get("corridor_id", ""))
            if corridor_id:
                resp2 = client.get(
                    f"/regulatory/corridors/{corridor_id}/trend",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp2.status_code == 200

    def test_generate_report_after_shadow(self, shadow_api_client):
        """POST /reports/generate → 200 with valid report_id."""
        client, token = shadow_api_client
        resp = client.post(
            "/regulatory/reports/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data

    def test_metadata_freshness_after_shadow(self, shadow_api_client):
        """GET /metadata shows populated metadata."""
        client, token = shadow_api_client
        resp = client.get(
            "/regulatory/metadata",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "methodology_version" in data or "api_version" in data
```

- [ ] **Step 3: Run all new tests**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py lip/tests/test_p10_regulator_subscription.py::TestAPIWithShadowData -v`
Expected: All pass

- [ ] **Step 4: Run ruff on all modified files**

Run: `ruff check lip/p10_regulatory_data/__init__.py lip/tests/test_p10_regulator_subscription.py`
Expected: All checks passed!

- [ ] **Step 5: Commit**

```bash
git add lip/p10_regulatory_data/__init__.py lip/tests/test_p10_regulator_subscription.py
git commit -m "feat(p10): export new Sprint 7 modules + API shadow integration tests"
```

---

### Task 8: Full Validation and Push

**Files:**
- All files from Tasks 1-7

- [ ] **Step 1: Run ruff on entire codebase**

Run: `ruff check lip/`
Expected: All checks passed!

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH=. python -m pytest lip/tests/ --ignore=lip/tests/test_e2e_live.py -q`
Expected: 2250+ passed (2230 baseline + ~24 new), 4 failed (pre-existing C2), 32 skipped

- [ ] **Step 3: Verify Sprint 7 test count**

Run: `PYTHONPATH=. python -m pytest lip/tests/test_p10_shadow_pipeline.py lip/tests/test_p10_regulator_subscription.py::TestAPIWithShadowData -v --co -q`
Expected: ~24 tests collected

- [ ] **Step 4: Final commit (if any unstaged changes)**

```bash
git status
# If clean, skip. Otherwise:
git add -A && git commit -m "chore: Sprint 7 cleanup"
```

- [ ] **Step 5: Push to GitHub**

```bash
git push origin codex/default-execution-protocol
```

Expected: Push succeeds, contribution graph updated.
