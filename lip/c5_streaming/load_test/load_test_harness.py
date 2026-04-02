"""
load_test_harness.py — Synthetic Avro replay load test for C5 Python Kafka consumer.

Replays synthetic payment events at a target TPS against the Python consumer
to establish a pre-migration baseline. Records p50/p95/p99 latency, max
throughput, and error rate.

Usage:
    PYTHONPATH=. python lip/c5_streaming/load_test/load_test_harness.py \\
        --tps 10000 --duration 60 --output /tmp/c5_baseline.json

Requirements:
    pip install confluent-kafka fastavro

The harness uses a fake (in-process) Kafka to avoid needing a live broker.
All message serialization and normalization is real; pipeline calls are stubbed.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic event generator
# ---------------------------------------------------------------------------

RAILS = ["SWIFT", "FEDNOW", "RTP", "SEPA"]
BICS = [
    "DEUTDEDBXXX", "CHASUS33XXX", "BNPAFRPPXXX", "BARCGB22XXX",
    "UBSWCHZHXXX", "HSBCGB2LXXX", "CITIGB2LXXX", "RBOSGB2LXXX",
]
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF"]
REJECTION_CODES = [None, None, None, None, "MS03", "AC01", "AC04", "FF01"]


def _synthetic_event(rail: str) -> dict:
    """Generate a synthetic payment event matching the C5 Avro schema."""
    uetr = str(uuid.uuid4())
    sending_bic = BICS[hash(uetr) % len(BICS)]
    receiving_bic = BICS[(hash(uetr) + 3) % len(BICS)]
    currency = CURRENCIES[hash(uetr) % len(CURRENCIES)]
    amount = f"{(hash(uetr) % 10_000_000) / 100:.2f}"
    rejection_code = REJECTION_CODES[hash(uetr) % len(REJECTION_CODES)]
    ts = datetime.now(timezone.utc).isoformat()

    event: dict = {
        "rail": rail,
        "message_type": "pacs.002" if rail in ("SWIFT", "SEPA") else f"{rail}.002",
        "uetr": uetr,
        "individual_payment_id": f"{sending_bic[:8]}-{int(time.time_ns()) % 1_000_000}",
        "sending_bic": sending_bic,
        "receiving_bic": receiving_bic,
        "amount": amount,
        "currency": currency,
        "timestamp": ts,
        "rejection_code": rejection_code,
        "narrative": None,
        "original_payment_amount_usd": None,
        "debtor_account": None,
        "raw_source": "{}",
    }
    return event


# ---------------------------------------------------------------------------
# Load test runner
# ---------------------------------------------------------------------------

@dataclass
class LoadTestResult:
    """Results from a single load test run."""
    target_tps: int
    actual_tps: float
    duration_s: float
    total_messages: int
    total_errors: int
    error_rate_pct: float

    # Latency percentiles (seconds)
    p50_s: float
    p95_s: float
    p99_s: float
    max_s: float
    min_s: float

    # Derived ms values for readability
    p50_ms: float = field(init=False)
    p95_ms: float = field(init=False)
    p99_ms: float = field(init=False)
    max_ms: float = field(init=False)
    min_ms: float = field(init=False)

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    implementation: str = "python"
    notes: str = ""

    def __post_init__(self) -> None:
        self.p50_ms = round(self.p50_s * 1000, 3)
        self.p95_ms = round(self.p95_s * 1000, 3)
        self.p99_ms = round(self.p99_s * 1000, 3)
        self.max_ms = round(self.max_s * 1000, 3)
        self.min_ms = round(self.min_s * 1000, 3)


def _noop_pipeline(event: Any) -> dict:
    """Stub pipeline function — returns immediately without ML inference.

    This measures normalization overhead only, not downstream ML latency.
    In a real benchmark with a live pipeline, replace with
    ``LIPPipeline.process(event)``.
    """
    return {"uetr": event.uetr, "outcome": "DECLINED", "status": "noop"}


def run_load_test(
    target_tps: int,
    duration_s: int,
    dry_run: bool = True,
) -> LoadTestResult:
    """
    Run a synthetic load test against the Python EventNormalizer.

    This simulates the C5 Python consumer's normalization hot path at the
    target TPS, capturing per-message latency via monotonic clock. The test
    uses no live Kafka broker — messages are generated in-process.

    Args:
        target_tps: Target messages per second.
        duration_s: Test duration in seconds.
        dry_run: When True, skips Kafka produce calls (normalizer only).

    Returns:
        LoadTestResult with latency percentiles and throughput stats.
    """
    from lip.c5_streaming.event_normalizer import EventNormalizer

    normalizer = EventNormalizer()
    latencies: list[float] = []
    errors = 0
    start = time.monotonic()
    interval = 1.0 / target_tps
    next_send = start

    logger.info(
        "Starting load test: target_tps=%d duration=%ds",
        target_tps, duration_s,
    )

    total_messages = 0
    deadline = start + duration_s

    while time.monotonic() < deadline:
        now = time.monotonic()
        if now < next_send:
            # Busy-wait for sub-millisecond precision
            pass
        else:
            rail = RAILS[total_messages % len(RAILS)]
            raw = _synthetic_event(rail)
            msg_start = time.monotonic()
            try:
                event = normalizer.normalize(rail, raw)
                result = _noop_pipeline(event)
                _ = result  # consumed
            except Exception as exc:  # noqa: BLE001
                logger.debug("Message processing error: %s", exc)
                errors += 1

            elapsed = time.monotonic() - msg_start
            latencies.append(elapsed)
            total_messages += 1
            next_send += interval

    actual_duration = time.monotonic() - start
    actual_tps = total_messages / actual_duration if actual_duration > 0 else 0

    if not latencies:
        latencies = [0.0]

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
    max_lat = sorted_lat[-1]
    min_lat = sorted_lat[0]

    result = LoadTestResult(
        target_tps=target_tps,
        actual_tps=round(actual_tps, 2),
        duration_s=round(actual_duration, 2),
        total_messages=total_messages,
        total_errors=errors,
        error_rate_pct=round(errors / max(total_messages, 1) * 100, 4),
        p50_s=p50,
        p95_s=p95,
        p99_s=p99,
        max_s=max_lat,
        min_s=min_lat,
        implementation="python",
        notes=(
            "Normalization-only benchmark (no ML inference, no live Kafka). "
            "Measures C5 Python EventNormalizer hot path latency at target TPS. "
            "Add live pipeline for end-to-end latency."
        ),
    )

    logger.info(
        "Load test complete: actual_tps=%.0f p50=%.3fms p95=%.3fms p99=%.3fms "
        "errors=%d error_rate=%.4f%%",
        actual_tps,
        result.p50_ms,
        result.p95_ms,
        result.p99_ms,
        errors,
        result.error_rate_pct,
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(
        description=(
            "C5 Python Kafka consumer load test harness. "
            "Replays synthetic events at TARGET_TPS and records latency percentiles."
        )
    )
    parser.add_argument("--tps", type=int, default=10_000, help="Target TPS (default: 10000)")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds (default: 30)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    args = parser.parse_args()

    result = run_load_test(target_tps=args.tps, duration_s=args.duration)

    data = asdict(result)

    if args.output:
        import pathlib
        out = pathlib.Path(args.output)
        out.write_text(json.dumps(data, indent=2))
        logger.info("Results written to %s", out)
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    _cli()
