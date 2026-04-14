"""Test for two-tier pricing floor (800 bps warehouse eligibility)."""
from lip.c2_pd_model.fee import compute_cascade_adjusted_pd
from lip.common.constants import (
    FEE_FLOOR_BPS,
    WAREHOUSE_ELIGIBILITY_FLOOR_BPS,
    is_spv_warehouse_eligible,
)


def test_spv_warehouse_eligible_meets_800_bps_floor():
    """Test that SPV warehouse-eligible loans (Phase 2/3) must be priced at or above 800 bps."""
    result = compute_cascade_adjusted_pd(
        base_pd="0.26",  # base_fee_bps = 1170, after 30% cascade discount: 819 bps (above 800 floor)
        cascade_value_prevented="9999999",
        intervention_cost="1",
    )

    # For SPV warehouse-eligible loans (phase_2 or phase_3), check against 800 bps
    is_spv_eligible = is_spv_warehouse_eligible(result.base_pd, "phase_2")
    expected_floor = WAREHOUSE_ELIGIBILITY_FLOOR_BPS
    actual_fee_bps = result.cascade_adjusted_fee_bps

    if is_spv_eligible:
        assert actual_fee_bps >= expected_floor, \
            f"CASCADE_ADJUSTED_FEE {actual_fee_bps} bps < WAREHOUSE_ELIGIBILITY_FLOOR_BPS {expected_floor} bps. " \
            f"SPV-eligible loan priced below warehouse floor."
    else:
        # For bank-funded loans or non-SPV-phase, platform floor (300 bps) applies
        assert actual_fee_bps >= FEE_FLOOR_BPS, \
            f"CASCADE_ADJUSTED_FEE {actual_fee_bps} bps < FEE_FLOOR_BPS {FEE_FLOOR_BPS} bps."
