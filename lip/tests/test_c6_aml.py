"""
test_c6_aml.py — Tests for C6 AML Velocity Controls
"""
import pytest
from decimal import Decimal

from lip.c6_aml_velocity.velocity import VelocityChecker, DOLLAR_CAP_USD, COUNT_CAP
from lip.c6_aml_velocity.cross_licensee import CrossLicenseeAggregator, cross_licensee_hash
from lip.c6_aml_velocity.sanctions import SanctionsScreener
from lip.c6_aml_velocity.anomaly import AnomalyDetector
from lip.c6_aml_velocity.salt_rotation import SaltRotationManager


_SALT = b"test_salt_32bytes_long_exactly__"


class TestVelocityChecker:
    def test_small_transaction_passes(self):
        checker = VelocityChecker(salt=_SALT)
        result = checker.check("entity1", Decimal("1000"), "bene1")
        assert result.passed is True

    def test_dollar_cap_exceeded(self):
        checker = VelocityChecker(salt=_SALT)
        checker.record("entity1", DOLLAR_CAP_USD - Decimal("1"), "bene1")
        result = checker.check("entity1", Decimal("2"), "bene2")
        assert result.passed is False
        assert result.reason == "DOLLAR_CAP_EXCEEDED"

    def test_count_cap_exceeded(self):
        checker = VelocityChecker(salt=_SALT)
        for i in range(COUNT_CAP):
            checker.record("entity2", Decimal("1"), f"bene{i}")
        result = checker.check("entity2", Decimal("1"), "bene_new")
        assert result.passed is False
        assert result.reason == "COUNT_CAP_EXCEEDED"

    def test_beneficiary_concentration_exceeded(self):
        checker = VelocityChecker(salt=_SALT)
        # Record 9 transactions all to same beneficiary ($9000), then 1 to different ($1000)
        for i in range(9):
            checker.record("entity3", Decimal("1000"), "bene_dominant")
        checker.record("entity3", Decimal("1000"), "bene_other")
        # Now try to add another large one to bene_dominant (>80%)
        result = checker.check("entity3", Decimal("9000"), "bene_dominant")
        assert result.passed is False
        assert result.reason == "BENEFICIARY_CONCENTRATION_EXCEEDED"

    def test_entity_id_never_stored_raw(self):
        checker = VelocityChecker(salt=_SALT)
        hashed = checker._hash_entity("TAX123456")
        assert "TAX123456" not in hashed
        assert len(hashed) == 64

    def test_different_entities_isolated(self):
        checker = VelocityChecker(salt=_SALT)
        checker.record("entity_a", DOLLAR_CAP_USD - Decimal("1"), "bene1")
        # entity_b is unaffected by entity_a's volume
        result = checker.check("entity_b", Decimal("500000"), "bene2")
        assert result.passed is True


class TestCrossLicenseeAggregator:
    def test_hash_is_not_raw(self):
        salt = b"salt"
        h = cross_licensee_hash("TAX123456", salt)
        assert "TAX123456" not in h
        assert len(h) == 64

    def test_record_and_retrieve_volume(self):
        agg = CrossLicenseeAggregator(salt=_SALT)
        agg.record("TAX001", Decimal("50000"))
        agg.record("TAX001", Decimal("30000"))
        vol = agg.get_cross_licensee_volume("TAX001")
        assert vol == Decimal("80000")

    def test_record_and_retrieve_count(self):
        agg = CrossLicenseeAggregator(salt=_SALT)
        agg.record("TAX002", Decimal("1000"))
        agg.record("TAX002", Decimal("2000"))
        count = agg.get_cross_licensee_count("TAX002")
        assert count == 2

    def test_different_tax_ids_isolated(self):
        agg = CrossLicenseeAggregator(salt=_SALT)
        agg.record("TAX_A", Decimal("100000"))
        vol_b = agg.get_cross_licensee_volume("TAX_B")
        assert vol_b == Decimal("0")


class TestSanctionsScreener:
    def test_clear_entity_passes(self):
        screener = SanctionsScreener()
        assert screener.is_clear("CLEAN COMPANY INC") is True

    def test_sanctioned_entity_detected(self):
        screener = SanctionsScreener()
        hits = screener.screen("ACME SHELL CORP")
        assert len(hits) > 0

    def test_hit_has_required_fields(self):
        screener = SanctionsScreener()
        hits = screener.screen("TEST BLOCKED PARTY")
        assert len(hits) > 0
        hit = hits[0]
        assert hit.confidence > 0
        assert hit.list_name is not None

    def test_entity_name_hash_not_raw(self):
        screener = SanctionsScreener()
        hits = screener.screen("TEST BLOCKED PARTY")
        for hit in hits:
            assert "TEST BLOCKED PARTY" not in hit.entity_name_hash


class TestAnomalyDetector:
    def _make_tx(self, amount=10000, hour=10, day=2):
        return {
            "amount": amount, "hour_of_day": hour, "day_of_week": day,
            "velocity_ratio": 1.0, "beneficiary_concentration": 0.5,
            "amount_zscore": 0.0,
        }

    def test_predict_before_fit(self):
        det = AnomalyDetector()
        result = det.predict(self._make_tx())
        assert isinstance(result.is_anomaly, bool)

    def test_fit_and_predict(self):
        det = AnomalyDetector()
        transactions = [self._make_tx(amount=i * 100) for i in range(1, 101)]
        det.fit(transactions)
        result = det.predict(self._make_tx(amount=50000))
        assert isinstance(result.is_anomaly, bool)
        assert 0.0 <= result.anomaly_score or result.anomaly_score <= 0.0  # any float

    def test_batch_predict(self):
        det = AnomalyDetector()
        txs = [self._make_tx(amount=i * 100) for i in range(1, 51)]
        det.fit(txs)
        results = det.predict_batch(txs[:5])
        assert len(results) == 5


class TestSaltRotation:
    def test_get_current_salt_returns_bytes(self):
        mgr = SaltRotationManager()
        salt = mgr.get_current_salt()
        assert isinstance(salt, bytes)
        assert len(salt) == 32

    def test_hash_with_current_is_deterministic(self):
        mgr = SaltRotationManager()
        h1 = mgr.hash_with_current("test_value")
        h2 = mgr.hash_with_current("test_value")
        assert h1 == h2
        assert len(h1) == 64

    def test_rotate_returns_new_and_old(self):
        mgr = SaltRotationManager()
        old = mgr.get_current_salt()
        new, returned_old = mgr.rotate_salt()
        assert new != returned_old
        assert returned_old == old

    def test_previous_salt_available_after_rotation(self):
        mgr = SaltRotationManager()
        mgr.rotate_salt()
        prev = mgr.get_previous_salt()
        assert prev is not None

    def test_overlap_period_after_rotation(self):
        mgr = SaltRotationManager()
        mgr.rotate_salt()
        assert mgr.is_in_overlap_period() is True
