"""
test_query_metering_budget_race.py — B3-01 regression test for TOCTOU race.

Before the 2026-04-09 fix, ``assert_within_budget`` acquired and released the
lock, then ``record_query`` took the lock again to increment.  Two threads at
budget-1 could both pass the check and both increment, exceeding the budget.

The fix makes the check-and-increment atomic: both happen inside a single
``self._lock`` hold in ``record_query``.

This test fires N=100 concurrent threads at a budget of K=10 and asserts that
exactly K queries are accepted and N-K are rejected.  It also verifies the
privacy-budget (epsilon) path with the same concurrency pattern.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from lip.c8_license_manager.query_metering import (
    PrivacyBudgetExceededError,
    QueryBudgetExceededError,
    RegulatoryQueryMetering,
)
from lip.c8_license_manager.regulator_subscription import RegulatorSubscriptionToken


def _make_token(
    *,
    query_budget: int = 1000,
    privacy_budget: float = 1000.0,
) -> RegulatorSubscriptionToken:
    now = datetime.now(timezone.utc)
    return RegulatorSubscriptionToken(
        regulator_id="REG-TEST-001",
        regulator_name="Test Regulator",
        subscription_tier="standard",
        permitted_corridors=None,
        query_budget_monthly=query_budget,
        privacy_budget_allocation=privacy_budget,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
    )


def _record_one(
    metering: RegulatoryQueryMetering,
    token: RegulatorSubscriptionToken,
    results: list,
    index: int,
    epsilon: float = 0.1,
) -> None:
    """Attempt one record_query; append True (accepted) or False (rejected)."""
    try:
        metering.record_query(
            token=token,
            endpoint="/api/v1/corridors",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=epsilon,
            response_latency_ms=10,
            billing_amount_usd=Decimal("0.50"),
        )
        results[index] = True
    except (QueryBudgetExceededError, PrivacyBudgetExceededError):
        results[index] = False


# ---------------------------------------------------------------------------
# Query-count budget race (B3-01 primary)
# ---------------------------------------------------------------------------


class TestQueryBudgetAtomicity:
    """N=100 threads, budget K=10 queries -> exactly 10 accepted."""

    N = 100
    K = 10

    def test_exactly_k_accepted(self):
        token = _make_token(query_budget=self.K)
        metering = RegulatoryQueryMetering(single_replica=True)
        results: list[bool | None] = [None] * self.N

        barrier = threading.Barrier(self.N)
        threads = []
        for i in range(self.N):
            t = threading.Thread(
                target=self._worker, args=(metering, token, results, i, barrier)
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=10)

        accepted = sum(1 for r in results if r is True)
        rejected = sum(1 for r in results if r is False)
        assert accepted == self.K, (
            f"Expected exactly {self.K} accepted queries, got {accepted}. "
            "B3-01 regression: TOCTOU race allowed over-budget queries."
        )
        assert rejected == self.N - self.K

    @staticmethod
    def _worker(metering, token, results, index, barrier):
        barrier.wait()
        _record_one(metering, token, results, index)


# ---------------------------------------------------------------------------
# Epsilon (privacy) budget race
# ---------------------------------------------------------------------------


class TestEpsilonBudgetAtomicity:
    """N=100 threads, each consuming epsilon=1.0, budget=10.0 -> exactly 10 accepted."""

    N = 100
    BUDGET = 10.0
    PER_QUERY = 1.0

    def test_exactly_budget_div_cost_accepted(self):
        expected_accepted = int(self.BUDGET / self.PER_QUERY)
        token = _make_token(privacy_budget=self.BUDGET)
        metering = RegulatoryQueryMetering(single_replica=True)
        results: list[bool | None] = [None] * self.N

        barrier = threading.Barrier(self.N)
        threads = []
        for i in range(self.N):
            t = threading.Thread(
                target=self._worker, args=(metering, token, results, i, barrier)
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=10)

        accepted = sum(1 for r in results if r is True)
        assert accepted == expected_accepted, (
            f"Expected exactly {expected_accepted} accepted queries under epsilon "
            f"budget {self.BUDGET}, got {accepted}. "
            "B3-01 regression: TOCTOU race on privacy budget."
        )


    @staticmethod
    def _worker(metering, token, results, index, barrier):
        barrier.wait()
        _record_one(metering, token, results, index, epsilon=TestEpsilonBudgetAtomicity.PER_QUERY)


# ---------------------------------------------------------------------------
# Sanity: sequential budget enforcement still works
# ---------------------------------------------------------------------------


def test_sequential_query_budget_enforced():
    """K queries succeed, K+1 raises QueryBudgetExceededError."""
    k = 5
    token = _make_token(query_budget=k)
    metering = RegulatoryQueryMetering(single_replica=True)
    for _ in range(k):
        metering.record_query(
            token=token,
            endpoint="/test",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=0.01,
            response_latency_ms=5,
            billing_amount_usd=Decimal("0.10"),
        )
    with pytest.raises(QueryBudgetExceededError):
        metering.record_query(
            token=token,
            endpoint="/test",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=0.01,
            response_latency_ms=5,
            billing_amount_usd=Decimal("0.10"),
        )


def test_sequential_epsilon_budget_enforced():
    """Epsilon budget exhaustion raises PrivacyBudgetExceededError."""
    token = _make_token(privacy_budget=2.0)
    metering = RegulatoryQueryMetering(single_replica=True)
    # Two queries at epsilon=1.0 each should succeed
    for _ in range(2):
        metering.record_query(
            token=token,
            endpoint="/test",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=1.0,
            response_latency_ms=5,
            billing_amount_usd=Decimal("0.10"),
        )
    # Third should fail
    with pytest.raises(PrivacyBudgetExceededError):
        metering.record_query(
            token=token,
            endpoint="/test",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=1.0,
            response_latency_ms=5,
            billing_amount_usd=Decimal("0.10"),
        )


def test_assert_within_budget_is_non_authoritative():
    """assert_within_budget is a fast-path pre-check, not the enforcement point.

    Verify that passing assert_within_budget does not guarantee record_query
    will also pass (i.e. the budget can be consumed between the two calls).
    This documents the B3-01 design: assert_within_budget is advisory only.
    """
    token = _make_token(query_budget=1)
    metering = RegulatoryQueryMetering(single_replica=True)

    # Pre-check passes
    metering.assert_within_budget(token=token, epsilon_cost=0.01)

    # Consume the budget
    metering.record_query(
        token=token,
        endpoint="/test",
        corridors_queried=["USD-EUR"],
        epsilon_consumed=0.01,
        response_latency_ms=5,
        billing_amount_usd=Decimal("0.10"),
    )

    # record_query rejects even though an earlier assert_within_budget passed
    with pytest.raises(QueryBudgetExceededError):
        metering.record_query(
            token=token,
            endpoint="/test",
            corridors_queried=["USD-EUR"],
            epsilon_consumed=0.01,
            response_latency_ms=5,
            billing_amount_usd=Decimal("0.10"),
        )
