"""
test_e2e_corridor.py — Corridor buffer bootstrap E2E tests.

Tests the 4-tier bootstrap model in pipeline context:
  - New corridor (Tier 0): uses conservative defaults from corridor_defaults.yaml
  - After 10 observations: graduates to Tier 1 (blended/conservative)
  - After 30+ observations: graduates to Tier 2 (blended empirical)
  - After 200 observations: graduates to Tier 3 (pure corridor P95)
  - Verify P95 estimation at each tier.
"""

from __future__ import annotations

import pytest

from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer, CorridorBufferDefaults


# ===========================================================================
# Tier graduation
# ===========================================================================

class TestCorridorBufferTiers:

    def test_tier_0_with_no_observations(self):
        cb = CorridorBuffer()
        assert cb.get_buffer_tier("USD_EUR") == 0

    def test_tier_1_with_10_observations(self):
        cb = CorridorBuffer()
        for _ in range(10):
            cb.add_observation("USD_EUR", 2.5)
        assert cb.get_buffer_tier("USD_EUR") == 1

    def test_tier_1_boundary_at_29_observations(self):
        cb = CorridorBuffer()
        for _ in range(29):
            cb.add_observation("USD_EUR", 3.0)
        assert cb.get_buffer_tier("USD_EUR") == 1

    def test_tier_2_at_30_observations(self):
        cb = CorridorBuffer()
        for _ in range(30):
            cb.add_observation("USD_GBP", 2.0)
        assert cb.get_buffer_tier("USD_GBP") == 2

    def test_tier_2_boundary_at_100_observations(self):
        cb = CorridorBuffer()
        for _ in range(100):
            cb.add_observation("USD_GBP", 2.0)
        assert cb.get_buffer_tier("USD_GBP") == 2

    def test_tier_3_at_101_observations(self):
        cb = CorridorBuffer()
        for _ in range(101):
            cb.add_observation("EUR_USD", 1.8)
        assert cb.get_buffer_tier("EUR_USD") == 3

    def test_tier_3_at_200_observations(self):
        """Verify early graduation at 200+ observations → pure P95."""
        cb = CorridorBuffer()
        for _ in range(200):
            cb.add_observation("GBP_USD", 4.0)
        assert cb.get_buffer_tier("GBP_USD") == 3


# ===========================================================================
# P95 estimation per tier
# ===========================================================================

class TestCorridorP95Estimation:

    def test_tier_0_uses_default(self):
        cb = CorridorBuffer()
        # USD_EUR default is 3.0
        p95 = cb.estimate_p95("USD_EUR")
        assert p95 == 3.0

    def test_tier_0_unknown_corridor_uses_default_fallback(self):
        cb = CorridorBuffer()
        p95 = cb.estimate_p95("UNKNOWN_CORRIDOR")
        assert p95 == 7.0  # DEFAULT key in corridor_defaults

    def test_tier_1_is_conservative(self):
        """Tier 1: default × 1.5 (conservative padding)."""
        cb = CorridorBuffer()
        for _ in range(10):
            cb.add_observation("USD_EUR", 2.0)
        p95 = cb.estimate_p95("USD_EUR")
        default = cb._defaults.get("USD_EUR")  # 3.0
        assert abs(p95 - default * 1.5) < 0.01

    def test_tier_2_blends_empirical_and_default(self):
        """Tier 2: 50% empirical + 50% default."""
        cb = CorridorBuffer()
        empirical_value = 5.0
        for _ in range(50):
            cb.add_observation("USD_EUR", empirical_value)
        p95 = cb.estimate_p95("USD_EUR")
        default = cb._defaults.get("USD_EUR")  # 3.0
        expected = 0.5 * empirical_value + 0.5 * default
        assert abs(p95 - expected) < 0.1

    def test_tier_3_uses_pure_empirical(self):
        """Tier 3: pure empirical P95."""
        cb = CorridorBuffer()
        values = list(range(1, 102))  # 1..101
        for v in values:
            cb.add_observation("EUR_USD", float(v))
        p95 = cb.estimate_p95("EUR_USD")
        import numpy as np
        expected = float(np.percentile(values, 95))
        assert abs(p95 - expected) < 0.1


# ===========================================================================
# Maturity extension
# ===========================================================================

class TestCorridorMaturityExtension:

    def test_tier_0_maturity_extension(self):
        cb = CorridorBuffer()
        import math
        ext = cb.get_maturity_extension("USD_EUR")
        assert ext == math.ceil(cb.estimate_p95("USD_EUR"))
        assert ext >= 1

    def test_tier_3_maturity_extension_from_data(self):
        cb = CorridorBuffer()
        for _ in range(200):
            cb.add_observation("USD_EUR", 4.5)
        ext = cb.get_maturity_extension("USD_EUR")
        assert ext == 5  # ceil(4.5) = 5


# ===========================================================================
# Serialisation round-trip
# ===========================================================================

class TestCorridorBufferSerialisation:

    def test_to_dict_and_from_dict(self):
        cb = CorridorBuffer()
        for i in range(50):
            cb.add_observation("USD_EUR", float(i % 7 + 1))
        d = cb.to_dict()
        cb2 = CorridorBuffer.from_dict(d)
        assert cb2.get_buffer_tier("USD_EUR") == cb.get_buffer_tier("USD_EUR")
        assert abs(cb2.estimate_p95("USD_EUR") - cb.estimate_p95("USD_EUR")) < 0.01
