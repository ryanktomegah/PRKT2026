"""
test_gap11_entity_tier_override.py — Tests for GAP-11:
Known-entity tier override for creditworthy banks with no LIP history.
"""
from unittest.mock import MagicMock

import pytest

from lip.api.portfolio_router import KnownEntityManager
from lip.c2_pd_model.inference import PDInferenceEngine
from lip.c2_pd_model.tier_assignment import Tier
from lip.common.known_entity_registry import KnownEntityRegistry


def _make_engine(registry=None):
    """Build a minimal PDInferenceEngine with mocked ML components.

    We only test _resolve_tier() here — the model and engineer are never
    called since we call _resolve_tier() directly without full inference.
    """
    model = MagicMock()
    engineer = MagicMock()
    engineer.tier = Tier.TIER_3
    return PDInferenceEngine(model, engineer, known_entity_registry=registry)


def _thin_file_borrower(bic: str = "") -> dict:
    """Borrower dict with no transaction history — would be Tier 3 without registry."""
    return {
        "bic": bic,
        "has_financial_statements": False,
        "has_transaction_history": False,
        "has_credit_bureau": False,
        "months_history": 0,
        "transaction_count": 0,
    }


# ---------------------------------------------------------------------------
# 1–5: KnownEntityRegistry unit tests
# ---------------------------------------------------------------------------

class TestKnownEntityRegistry:
    def test_lookup_returns_none_for_unknown_bic(self):
        """Fresh registry returns None for any BIC."""
        registry = KnownEntityRegistry()
        assert registry.lookup("ANYBANK") is None

    def test_register_and_lookup(self):
        """Registered BIC returns the assigned tier."""
        registry = KnownEntityRegistry()
        registry.register("JPMORGAN", Tier.TIER_1)
        assert registry.lookup("JPMORGAN") == Tier.TIER_1

    def test_lookup_is_case_insensitive(self):
        """BIC lookup is case-insensitive; 'jpmorgan' finds 'JPMORGAN'."""
        registry = KnownEntityRegistry()
        registry.register("JPMORGAN", Tier.TIER_1)
        assert registry.lookup("jpmorgan") == Tier.TIER_1
        assert registry.lookup("JpMoRgAn") == Tier.TIER_1

    def test_unregister_removes_override(self):
        """Unregistering a BIC causes subsequent lookup to return None."""
        registry = KnownEntityRegistry()
        registry.register("DEUTDEDB", Tier.TIER_1)
        registry.unregister("DEUTDEDB")
        assert registry.lookup("DEUTDEDB") is None

    def test_is_registered_reflects_state(self):
        """is_registered returns True after register, False after unregister."""
        registry = KnownEntityRegistry()
        assert not registry.is_registered("BARCGB22")
        registry.register("BARCGB22", Tier.TIER_1)
        assert registry.is_registered("BARCGB22")
        registry.unregister("BARCGB22")
        assert not registry.is_registered("BARCGB22")


# ---------------------------------------------------------------------------
# 6–10: PDInferenceEngine._resolve_tier with registry
# ---------------------------------------------------------------------------

class TestPDInferenceEngineWithRegistry:
    def test_inference_uses_registry_override_for_tier1(self):
        """Thin-file borrower registered as Tier 1 → _resolve_tier returns TIER_1."""
        registry = KnownEntityRegistry()
        registry.register("JPMCHASE", Tier.TIER_1)
        engine = _make_engine(registry)
        assert engine._resolve_tier(_thin_file_borrower("JPMCHASE")) == Tier.TIER_1

    def test_inference_uses_registry_override_for_tier2(self):
        """Thin-file borrower registered as Tier 2 → _resolve_tier returns TIER_2."""
        registry = KnownEntityRegistry()
        registry.register("COMMERZB", Tier.TIER_2)
        engine = _make_engine(registry)
        assert engine._resolve_tier(_thin_file_borrower("COMMERZB")) == Tier.TIER_2

    def test_no_registry_thin_file_falls_back_to_tier3(self):
        """Without registry, thin-file borrower → TIER_3 via data-availability rule."""
        engine = _make_engine(registry=None)
        assert engine._resolve_tier(_thin_file_borrower()) == Tier.TIER_3

    def test_known_bank_gets_tier1_not_tier3(self):
        """Registry override prevents the 900+ bps thin-file penalty for known banks."""
        registry = KnownEntityRegistry()
        registry.register("BARCGB22", Tier.TIER_1)
        engine = _make_engine(registry)
        tier = engine._resolve_tier(_thin_file_borrower("BARCGB22"))
        assert tier == Tier.TIER_1
        assert int(tier) < 3  # confirm NOT tier 3

    def test_registry_override_does_not_affect_unregistered_bic(self):
        """Registry presence doesn't change tier for BICs not in the override list."""
        registry = KnownEntityRegistry()
        registry.register("REGISTERED", Tier.TIER_1)
        engine = _make_engine(registry)
        # Unregistered BIC → normal data-availability rule applies (thin-file → TIER_3)
        assert engine._resolve_tier(_thin_file_borrower("UNREGISTERED")) == Tier.TIER_3


# ---------------------------------------------------------------------------
# 11–12: KnownEntityManager (portfolio API layer)
# ---------------------------------------------------------------------------

class TestKnownEntityManager:
    @pytest.fixture
    def manager(self):
        return KnownEntityManager(KnownEntityRegistry())

    def test_list_entities_initially_empty(self, manager):
        """Fresh manager returns an empty list."""
        assert manager.list_entities() == []

    def test_register_appears_in_list(self, manager):
        """Registered entity appears in list_entities output."""
        manager.register("CITIBANK", 1)
        entities = manager.list_entities()
        assert len(entities) == 1
        assert entities[0]["bic"] == "CITIBANK"
        assert entities[0]["tier"] == 1

    def test_register_and_delete_entity(self, manager):
        """POST then DELETE: entity present then absent."""
        result = manager.register("HSBCGB2L", 1)
        assert result["status"] == "registered"
        assert result["bic"] == "HSBCGB2L"

        entities_before = manager.list_entities()
        assert any(e["bic"] == "HSBCGB2L" for e in entities_before)

        delete_result = manager.unregister("HSBCGB2L")
        assert delete_result["status"] == "unregistered"

        entities_after = manager.list_entities()
        assert not any(e["bic"] == "HSBCGB2L" for e in entities_after)
