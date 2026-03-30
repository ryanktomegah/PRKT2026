"""
test_regulatory_api.py — TDD tests for P10 Regulatory API.

Sprint 4c: HTTP REST endpoints over Sprint 4b systemic risk engine.
"""
from __future__ import annotations


class TestRateLimiter:
    """Token-bucket rate limiter tests."""

    def test_fresh_bucket_allows_request(self):
        """New key starts at full capacity — first request allowed."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, period_seconds=3600)
        assert limiter.check_and_consume("key-1") is True

    def test_exhaust_bucket_rejects(self):
        """After consuming all tokens, next request rejected."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=3, period_seconds=3600)
        for _ in range(3):
            assert limiter.check_and_consume("key-1") is True
        assert limiter.check_and_consume("key-1") is False

    def test_different_keys_independent(self):
        """Different keys have separate buckets."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=2, period_seconds=3600)
        limiter.check_and_consume("key-A")
        limiter.check_and_consume("key-A")
        assert limiter.check_and_consume("key-A") is False
        assert limiter.check_and_consume("key-B") is True

    def test_tokens_refill_after_period(self):
        """Tokens refill proportionally as time passes."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, period_seconds=10)
        for _ in range(10):
            limiter.check_and_consume("key-1")
        assert limiter.check_and_consume("key-1") is False
        with limiter._lock:
            tokens, last_refill = limiter._buckets["key-1"]
            limiter._buckets["key-1"] = (tokens, last_refill - 5.0)
        assert limiter.check_and_consume("key-1") is True

    def test_remaining_returns_correct_count(self):
        """remaining() reflects tokens left."""
        from lip.api.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=5, period_seconds=3600)
        assert limiter.remaining("key-1") == 5
        limiter.check_and_consume("key-1")
        assert limiter.remaining("key-1") == 4
