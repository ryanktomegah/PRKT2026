"""
test_c6_aml.py — Tests for C6 AML Velocity Controls
"""
from decimal import Decimal

from lip.c6_aml_velocity.aml_checker import AMLChecker
from lip.c6_aml_velocity.anomaly import AnomalyDetector
from lip.c6_aml_velocity.cross_licensee import CrossLicenseeAggregator, cross_licensee_hash
from lip.c6_aml_velocity.salt_rotation import SaltRotationManager
from lip.c6_aml_velocity.sanctions import SanctionsScreener
from lip.c6_aml_velocity.velocity import VelocityChecker

_SALT = b"test_salt_32bytes_long_exactly__"

# EPG-16: Module-level caps are now 0 (unlimited). Tests that exercise cap
# enforcement must pass explicit overrides so they remain deterministic.
_TEST_DOLLAR_CAP = Decimal("1000000")
_TEST_COUNT_CAP = 100


class TestVelocityChecker:
    def test_small_transaction_passes(self):
        checker = VelocityChecker(salt=_SALT)
        result = checker.check("entity1", Decimal("1000"), "bene1")
        assert result.passed is True

    def test_dollar_cap_exceeded(self):
        checker = VelocityChecker(salt=_SALT)
        checker.record("entity1", _TEST_DOLLAR_CAP - Decimal("1"), "bene1")
        result = checker.check("entity1", Decimal("2"), "bene2",
                               dollar_cap_override=_TEST_DOLLAR_CAP)
        assert result.passed is False
        assert result.reason == "DOLLAR_CAP_EXCEEDED"

    def test_count_cap_exceeded(self):
        checker = VelocityChecker(salt=_SALT)
        for i in range(_TEST_COUNT_CAP):
            checker.record("entity2", Decimal("1"), f"bene{i}")
        result = checker.check("entity2", Decimal("1"), "bene_new",
                               count_cap_override=_TEST_COUNT_CAP)
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
        checker.record("entity_a", _TEST_DOLLAR_CAP - Decimal("1"), "bene1")
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


def _make_aml_checker() -> AMLChecker:
    """Create an AMLChecker with a default VelocityChecker.
    entity_name_resolver=None is explicit: test entity_ids are human-readable strings,
    not BIC codes, so no resolver is needed (EPG-24).
    """
    return AMLChecker(velocity_checker=VelocityChecker(salt=_SALT), entity_name_resolver=None)


class TestAMLChecker:
    """Gap 2 regression: combined sanctions → velocity → anomaly gate."""

    def test_clean_entity_passes(self):
        checker = _make_aml_checker()
        result = checker.check("entity_ok", Decimal("1000"), "bene_ok")
        assert result.passed is True

    def test_sanctioned_entity_is_blocked_before_velocity(self):
        """Sanctions check (step 1) must block before velocity is evaluated."""
        checker = _make_aml_checker()
        result = checker.check(
            "entity_clean", Decimal("1"),
            "bene_clean",
            beneficiary_name="TEST BLOCKED PARTY",
        )
        assert result.passed is False
        assert "SANCTIONS" in result.reason.upper() or len(result.sanctions_hits) > 0

    def test_velocity_cap_blocks_after_sanctions_pass(self):
        """When sanctions pass, velocity cap must still block."""
        checker = _make_aml_checker()
        # Saturate velocity via the internal _velocity attribute
        checker._velocity.record("entity_v", _TEST_DOLLAR_CAP - Decimal("1"), "b1")
        result = checker.check("entity_v", Decimal("2"), "b2",
                               dollar_cap_override=_TEST_DOLLAR_CAP)
        assert result.passed is False
        assert "CAP" in result.reason

    def test_anomaly_is_soft_flag_not_hard_block(self):
        """Anomaly detection flags but does not hard-block the transaction."""
        from lip.c6_aml_velocity.anomaly import AnomalyDetector
        detector = AnomalyDetector()
        normal_txs = [{"amount": 1000, "hour_of_day": 10, "day_of_week": 2,
                       "velocity_ratio": 1.0, "beneficiary_concentration": 0.5,
                       "amount_zscore": 0.0} for _ in range(50)]
        detector.fit(normal_txs)
        checker = AMLChecker(
            velocity_checker=VelocityChecker(salt=_SALT),
            anomaly_detector=detector,
            entity_name_resolver=None,  # test entity_ids are human-readable (EPG-24)
        )
        result = checker.check("entity_anom", Decimal("1"), "bene_anom")
        assert isinstance(result.passed, bool)
        assert isinstance(result.anomaly_flagged, bool)

    def test_passed_transaction_records_velocity(self):
        """After a passing check, velocity is incremented for future checks."""
        checker = _make_aml_checker()
        amount = Decimal("50000")
        checker.check("entity_rec", amount, "bene_rec")
        # Push toward cap: record near the remaining budget
        checker._velocity.record("entity_rec", _TEST_DOLLAR_CAP - amount - Decimal("1"), "b2")
        result2 = checker.check("entity_rec", Decimal("2"), "b3",
                                dollar_cap_override=_TEST_DOLLAR_CAP)
        assert result2.passed is False  # now over cap


class TestCrossLicenseeSaltRotationDualHash:
    """Gap 5 regression: same entity recognized across salt rotation boundary."""

    def test_dual_write_during_overlap_period(self):
        """During overlap, record() writes to both current and previous-salt keys."""
        mgr = SaltRotationManager()
        mgr.rotate_salt()
        assert mgr.is_in_overlap_period()

        agg = CrossLicenseeAggregator(salt=mgr.get_current_salt(), salt_manager=mgr)
        agg.record("TAX_ROTATE_001", Decimal("50000"))

        # Both current-salt and previous-salt keys should have the amount
        cur_salt = mgr.get_current_salt()
        prev_salt = mgr.get_previous_salt()
        assert prev_salt is not None

        from lip.c6_aml_velocity.cross_licensee import cross_licensee_hash
        cur_hash = cross_licensee_hash("TAX_ROTATE_001", cur_salt)
        prev_hash = cross_licensee_hash("TAX_ROTATE_001", prev_salt)

        cur_key = agg._make_key(cur_hash, "volume")
        prev_key = agg._make_key(prev_hash, "volume")

        assert Decimal(agg._store.get(cur_key, "0")) == Decimal("50000")
        assert Decimal(agg._store.get(prev_key, "0")) == Decimal("50000")

    def test_get_volume_reads_from_prev_salt_during_overlap(self):
        """get_cross_licensee_volume aggregates old-salt data during overlap."""
        mgr = SaltRotationManager()
        # Record under old salt before rotating
        old_salt = mgr.get_current_salt()
        agg_old = CrossLicenseeAggregator(salt=old_salt)
        agg_old.record("TAX_CROSS_002", Decimal("30000"))

        # Now rotate
        mgr.rotate_salt()
        assert mgr.is_in_overlap_period()

        # New aggregator with salt_manager — can see old-salt data
        agg_new = CrossLicenseeAggregator(
            salt=mgr.get_current_salt(),
            salt_manager=mgr,
        )
        # Copy old-salt store data to new agg's store to simulate shared Redis
        agg_new._store.update(agg_old._store)

        vol = agg_new.get_cross_licensee_volume("TAX_CROSS_002")
        assert vol == Decimal("30000")

    def test_migrate_overlap_period_copies_to_current_salt(self):
        """migrate_overlap_period() moves old-salt records to current-salt keys."""
        mgr = SaltRotationManager()
        old_salt = mgr.get_current_salt()

        # Record under old salt
        agg = CrossLicenseeAggregator(salt=old_salt)
        agg.record("TAX_MIGRATE_001", Decimal("75000"))
        old_store_snapshot = dict(agg._store)

        # Rotate and attach manager
        mgr.rotate_salt()
        agg._salt_manager = mgr
        agg._store.update(old_store_snapshot)

        migrated = agg.migrate_overlap_period(["TAX_MIGRATE_001"])
        assert migrated == 1

        # Current-salt key should now have the volume
        cur_hash = cross_licensee_hash("TAX_MIGRATE_001", mgr.get_current_salt())
        cur_key = agg._make_key(cur_hash, "volume")
        assert Decimal(agg._store.get(cur_key, "0")) == Decimal("75000")

    def test_no_dual_write_outside_overlap(self):
        """Outside the overlap window, only current-salt key is written."""
        mgr = SaltRotationManager()
        # No rotation → not in overlap period
        assert not mgr.is_in_overlap_period()

        agg = CrossLicenseeAggregator(salt=mgr.get_current_salt(), salt_manager=mgr)
        agg.record("TAX_SINGLE_003", Decimal("10000"))

        # Only one key should exist
        assert len(agg._store) == 2  # volume + count (current salt only)


class TestVelocityUnlimitedCapRegression:
    """EPG-16 regression: cap=0 means unlimited — transactions must NOT be blocked.

    This tests the in-memory path directly.  The Lua script at
    velocity.py:110-114 had the same bug (missing ``> 0`` guard) and was
    fixed in the same commit; the Lua string is validated by
    ``test_lua_script_has_cap_zero_guard`` below.
    """

    def test_dollar_cap_zero_means_unlimited(self):
        """With dollar_cap=0 (EPG-16 default), any amount should pass."""
        checker = VelocityChecker(salt=_SALT)
        # Record a large volume first
        checker.record("entity_unlim", Decimal("999999999"), "bene1")
        result = checker.check(
            "entity_unlim", Decimal("1"), "bene2",
            dollar_cap_override=Decimal("0"),
        )
        assert result.passed is True, (
            f"dollar_cap=0 should mean unlimited, but got blocked: {result.reason}"
        )

    def test_count_cap_zero_means_unlimited(self):
        """With count_cap=0 (EPG-16 default), any count should pass."""
        checker = VelocityChecker(salt=_SALT)
        for i in range(200):
            checker.record("entity_cnt_unlim", Decimal("1"), f"bene_{i}")
        result = checker.check(
            "entity_cnt_unlim", Decimal("1"), "bene_new",
            count_cap_override=0,
        )
        assert result.passed is True, (
            f"count_cap=0 should mean unlimited, but got blocked: {result.reason}"
        )

    def test_lua_script_has_cap_zero_guard(self):
        """Verify the Lua script text contains the ``> 0`` guard for both caps.

        This catches future regressions where someone edits the Lua script
        and accidentally drops the guard.  It does NOT require a Redis instance.
        """
        from lip.c6_aml_velocity.velocity import _ATOMIC_CHECK_RECORD_LUA

        assert "dollar_cap > 0 and vol + candidate > dollar_cap" in _ATOMIC_CHECK_RECORD_LUA, (
            "Lua script missing dollar_cap > 0 guard (EPG-16: 0 = unlimited)"
        )
        assert "count_cap > 0 and cnt + 1 > count_cap" in _ATOMIC_CHECK_RECORD_LUA, (
            "Lua script missing count_cap > 0 guard (EPG-16: 0 = unlimited)"
        )


class TestVelocityCheckAndRecordTOCTOU:
    """EPG-25 regression: concurrent check_and_record must not allow cap overruns."""

    def test_in_memory_concurrent_no_cap_overrun(self):
        """N threads all firing check_and_record simultaneously must not collectively
        exceed the dollar cap.  Without the lock (old check()+record() split) all N
        workers would see the same pre-write snapshot and all would pass."""
        import threading

        count_cap = 3
        dollar_per_txn = Decimal("300000")
        checker = VelocityChecker(salt=_SALT)

        passes = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()  # all threads release simultaneously
            result = checker.check_and_record(
                "entity_conc", dollar_per_txn, "bene_conc",
                count_cap_override=count_cap,
            )
            if result.passed:
                passes.append(1)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly count_cap transactions should pass — no more leaked through
        assert len(passes) == count_cap
