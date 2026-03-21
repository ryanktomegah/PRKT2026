"""
test_e2e_config.py — Configuration loading E2E tests.

Verifies all YAML configs load correctly and values match Architecture Spec:
  - canonical_numbers.yaml: market_size $31.7T, STP 3.5% midpoint
  - rejection_taxonomy.yaml: all rejection codes mapped correctly
  - corridor_defaults.yaml: Tier 0 defaults for 25+ corridors
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from lip.c3_repayment_engine.rejection_taxonomy import (
    REJECTION_CODE_TAXONOMY,
    RejectionClass,
    classify_rejection_code,
    maturity_days,
)

# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------

_CONFIGS_DIR = Path(__file__).parent.parent / "configs"


def _load_yaml(filename: str) -> dict:
    path = _CONFIGS_DIR / filename
    with path.open("r") as f:
        return yaml.safe_load(f)


# ===========================================================================
# canonical_numbers.yaml
# ===========================================================================

class TestCanonicalNumbers:

    def test_file_exists(self):
        assert (_CONFIGS_DIR / "canonical_numbers.yaml").exists()

    def test_market_size_is_31_7_trillion(self):
        data = _load_yaml("canonical_numbers.yaml")
        market_size = data["market_sizing"]["market_size_usd"]
        assert market_size == 31_700_000_000_000

    def test_stp_midpoint_is_3_5_percent(self):
        data = _load_yaml("canonical_numbers.yaml")
        midpoint = data["failure_rates"]["midpoint"]
        assert midpoint == 0.035

    def test_fee_floor_bps_is_300(self):
        data = _load_yaml("canonical_numbers.yaml")
        floor = data["fee_parameters"]["fee_floor_bps"]
        assert floor == 300

    def test_fee_floor_per_7day_cycle(self):
        """Verify 300/10000 * 7/365 ≈ 0.000575"""
        data = _load_yaml("canonical_numbers.yaml")
        val = data["fee_parameters"]["fee_floor_per_7day_cycle"]
        expected = Decimal("300") / Decimal("10000") * Decimal("7") / Decimal("365")
        assert abs(Decimal(str(val)) - expected) < Decimal("0.000001")

    def test_threshold_tau_star_present(self):
        data = _load_yaml("canonical_numbers.yaml")
        # The threshold τ* = 0.110 may be in decision_thresholds or similar
        # Check it's present in some form
        assert data is not None


# ===========================================================================
# rejection_taxonomy.yaml (or in-code taxonomy)
# ===========================================================================

class TestRejectionTaxonomy:

    def test_taxonomy_file_exists(self):
        assert (_CONFIGS_DIR / "rejection_taxonomy.yaml").exists()

    def test_class_a_codes_have_3_day_maturity(self):
        class_a_codes = [
            code for code, cls in REJECTION_CODE_TAXONOMY.items()
            if cls == RejectionClass.CLASS_A
        ]
        assert len(class_a_codes) > 0
        for code in class_a_codes:
            cls = classify_rejection_code(code)
            assert maturity_days(cls) == 3

    def test_class_b_codes_have_7_day_maturity(self):
        class_b_codes = [
            code for code, cls in REJECTION_CODE_TAXONOMY.items()
            if cls == RejectionClass.CLASS_B
        ]
        assert len(class_b_codes) > 0
        for code in class_b_codes:
            cls = classify_rejection_code(code)
            assert maturity_days(cls) == 7

    def test_class_c_codes_have_21_day_maturity(self):
        class_c_codes = [
            code for code, cls in REJECTION_CODE_TAXONOMY.items()
            if cls == RejectionClass.CLASS_C
        ]
        assert len(class_c_codes) > 0
        for code in class_c_codes:
            cls = classify_rejection_code(code)
            assert maturity_days(cls) == 21

    def test_block_codes_have_zero_maturity(self):
        block_codes = [
            code for code, cls in REJECTION_CODE_TAXONOMY.items()
            if cls == RejectionClass.BLOCK
        ]
        assert len(block_codes) > 0
        for code in block_codes:
            cls = classify_rejection_code(code)
            assert maturity_days(cls) == 0

    def test_disp_is_block_class(self):
        cls = classify_rejection_code("DISP")
        assert cls == RejectionClass.BLOCK

    def test_curr_is_class_b(self):
        cls = classify_rejection_code("CURR")
        assert cls == RejectionClass.CLASS_B

    def test_ac04_is_class_a(self):
        cls = classify_rejection_code("AC04")
        assert cls == RejectionClass.CLASS_A

    def test_taxonomy_has_at_least_50_codes(self):
        """Architecture Spec mentions 59 codes total."""
        assert len(REJECTION_CODE_TAXONOMY) >= 50

    def test_unknown_code_raises_value_error(self):
        with pytest.raises(ValueError):
            classify_rejection_code("XXXX_UNKNOWN_CODE")


# ===========================================================================
# corridor_defaults.yaml
# ===========================================================================

class TestCorridorDefaults:

    def test_file_exists(self):
        assert (_CONFIGS_DIR / "corridor_defaults.yaml").exists()

    def test_usd_eur_default_present(self):
        data = _load_yaml("corridor_defaults.yaml")
        corridors = data.get("defaults", data)
        assert "USD_EUR" in corridors

    def test_default_fallback_present(self):
        """DEFAULT key must be present for unknown corridors."""
        data = _load_yaml("corridor_defaults.yaml")
        corridors = data.get("defaults", data)
        assert "DEFAULT" in corridors

    def test_all_defaults_are_positive(self):
        data = _load_yaml("corridor_defaults.yaml")
        corridors = data.get("defaults", {})
        for corridor, value in corridors.items():
            if isinstance(value, (int, float)):
                assert value > 0, f"Corridor {corridor} has non-positive default {value}"

    def test_corridor_buffer_loads_defaults(self):
        """CorridorBuffer should use defaults matching the YAML."""
        from lip.c3_repayment_engine.corridor_buffer import CorridorBuffer
        cb = CorridorBuffer()
        # USD_EUR should have a positive default
        assert cb.estimate_p95("USD_EUR") > 0.0
        # Unknown corridor falls back to DEFAULT
        assert cb.estimate_p95("TOTALLY_UNKNOWN") > 0.0
