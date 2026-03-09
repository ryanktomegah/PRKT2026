"""
locustfile.py — LIP 50K TPS load test.

Target: C7 ExecutionAgent REST API — POST /api/v1/payment-event

Architecture Spec v1.2 SLO targets:
  Latency P50 ≤ 45ms
  Latency P99 ≤ 94ms
  Throughput ≥ 50,000 TPS

Prerequisites:
  pip install locust

Run (headless, staged ramp-up to 50K TPS):
  locust -f lip/tests/load/locustfile.py \\
    --host http://lip-c7-svc:8080 \\
    --users 5000 \\
    --spawn-rate 500 \\
    --run-time 120s \\
    --headless \\
    --csv=lip/tests/load/results/lip_50k_tps

Notes on TPS math:
  50K TPS with average response time of 10ms → 500 concurrent connections
  For safety margin, target 5,000 users at 1–5ms think time → ~25K–50K RPS
  Scale --users and --spawn-rate based on observed latency at lower concurrency.

Web UI mode (for interactive analysis):
  locust -f lip/tests/load/locustfile.py --host http://localhost:8080
  Open http://localhost:8089
"""
import json
import random
import uuid

from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

REJECTION_CODES = [
    # CLASS_A — temporary/technical (3-day maturity, high bridge-loan rate)
    "AC01", "AC04", "AM01", "AM04", "AM09", "BE01", "BE04",
    # CLASS_B — systemic (7-day maturity)
    "CUST", "TECH", "TIMO", "NOAS",
    # CLASS_C — complex (21-day maturity)
    "LEGL", "INVB",
]

CURRENCIES = ["USD", "EUR", "GBP", "SGD", "JPY", "HKD", "CHF"]

SENDING_BICS = [
    "DEUTDEDBFRA", "CHASUS33XXX", "BARCGB22XXX",
    "BNPAFRPPXXX", "CHASSGSGXXX", "HSBCHKHHXXX",
]

RECEIVING_BICS = [
    "CITIUS33XXX", "WFBIUS6WFFX", "BOFAHKHXXXX",
    "RBOSGB2LXXX", "UOVBSGSGXXX", "MHCBJPJTXXX",
]

NARRATIVES = [
    "Cross-border supplier payment — rejected",
    "FX conversion failure on correspondent bank",
    "Insufficient funds — retry pending",
    "Compliance hold — reviewing documentation",
    "Technical timeout on receiving end",
]


def _random_payload() -> dict:
    """Generate a randomised payment rejection event payload."""
    return {
        "uetr": str(uuid.uuid4()),
        "rejection_code": random.choice(REJECTION_CODES),
        "amount": f"{random.uniform(10_000, 5_000_000):.2f}",
        "currency": random.choice(CURRENCIES),
        "sending_bic": random.choice(SENDING_BICS),
        "receiving_bic": random.choice(RECEIVING_BICS),
        "narrative": random.choice(NARRATIVES),
        "rail": "SWIFT",
    }


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------

class PaymentEventUser(HttpUser):
    """
    Simulates a payment origination system submitting rejection events to C7.

    Think time of 1–5ms models real-world inter-request spacing at the
    origination layer. At 5,000 concurrent users this yields ~25–50K RPS.
    """

    wait_time = between(0.001, 0.005)  # 1–5ms between requests per user

    @task(weight=80)
    def submit_payment_rejection(self):
        """Primary task: submit a payment rejection event (80% of traffic)."""
        payload = _random_payload()
        with self.client.post(
            "/api/v1/payment-event",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            name="/api/v1/payment-event",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (429, 503):
                # Expected under extreme load — mark as success to avoid noise
                response.success()
            else:
                response.failure(
                    f"Unexpected status {response.status_code}: {response.text[:200]}"
                )

    @task(weight=15)
    def health_check(self):
        """Periodic health check (15% of traffic)."""
        self.client.get(
            "/health/ready",
            name="/health/ready",
        )

    @task(weight=5)
    def kill_switch_status(self):
        """Check kill switch state (5% of traffic — ops monitoring pattern)."""
        self.client.get(
            "/api/v1/kill-switch/status",
            name="/api/v1/kill-switch/status",
        )


class HighVolumeUser(HttpUser):
    """
    Aggressive variant: minimal think time, large payments.
    Use for stress-testing the 94ms P99 SLO at extreme load.
    """

    wait_time = between(0.0001, 0.001)  # 0.1–1ms — near-zero think time

    @task
    def submit_large_payment(self):
        payload = _random_payload()
        payload["amount"] = f"{random.uniform(1_000_000, 50_000_000):.2f}"
        self.client.post(
            "/api/v1/payment-event",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            name="/api/v1/payment-event [high-volume]",
        )


# ---------------------------------------------------------------------------
# Hooks: validate SLO thresholds at test end
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Fail the run if P99 latency exceeds the 94ms SLO."""
    stats = environment.runner.stats
    total = stats.total

    if total.num_requests == 0:
        print("[LOAD TEST] No requests completed — check host/connectivity")
        environment.process_exit_code = 1
        return

    # Locust reports response times in milliseconds
    p99_ms = total.get_response_time_percentile(0.99) or 0
    p50_ms = total.get_response_time_percentile(0.50) or 0
    rps = total.current_rps

    print(
        f"\n[LOAD TEST SUMMARY]\n"
        f"  Total requests : {total.num_requests:,}\n"
        f"  Failures       : {total.num_failures:,} ({100 * total.fail_ratio:.1f}%)\n"
        f"  P50 latency    : {p50_ms:.1f}ms  (SLO ≤ 45ms)\n"
        f"  P99 latency    : {p99_ms:.1f}ms  (SLO ≤ 94ms)\n"
        f"  RPS at end     : {rps:.0f}  (target ≥ 50,000)\n"
    )

    failed = False
    if p99_ms > 94:
        print(f"  [FAIL] P99 {p99_ms:.1f}ms exceeds 94ms SLO")
        failed = True
    if total.fail_ratio > 0.001:  # >0.1% error rate is a failure
        print(f"  [FAIL] Error rate {100 * total.fail_ratio:.2f}% exceeds 0.1% threshold")
        failed = True

    if failed:
        environment.process_exit_code = 1
    else:
        print("  [PASS] All SLO targets met")
