"""
cross_licensee.py — SHA-256 hashed cross-licensee velocity aggregation.
Privacy-preserving: entities cannot be de-anonymized across licensees.

Architecture Spec S11.3: During the 30-day salt-rotation overlap window,
both the current and previous salts are used to record and look up velocity
data, so the same entity is not counted as two different entities.

Three-entity role mapping:
  MLO  — Money Lending Organisation
  MIPLO — Money In / Payment Lending Organisation
  ELO  — Execution Lending Organisation (bank-side agent, C7)
"""
import hashlib
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


def cross_licensee_hash(tax_id: str, salt: bytes) -> str:
    """SHA-256(tax_id + salt). Hex digest. Never returns raw tax_id."""
    return hashlib.sha256(tax_id.encode() + salt).hexdigest()


class CrossLicenseeAggregator:
    """Aggregates velocity across licensees using privacy-preserving hashes.

    During the 30-day salt-rotation overlap period (Architecture Spec S11.3),
    reads aggregate across both current-salt and previous-salt keys so that an
    entity recorded under the old salt is still recognised.  Writes update both
    keys simultaneously to keep the stores in sync throughout the window.

    Parameters
    ----------
    salt:
        Primary (current) salt bytes.  Superseded by ``salt_manager`` when
        provided — ``salt`` is then used only as a fallback if the manager
        has no current salt loaded.
    shared_redis_client:
        Optional Redis client for cross-process shared state.
    salt_manager:
        Optional :class:`SaltRotationManager`.  When provided, the aggregator
        uses the manager to obtain current/previous salts and detect the
        overlap period instead of using the fixed ``salt`` value.
    """

    def __init__(
        self,
        salt: bytes,
        shared_redis_client=None,
        salt_manager=None,
    ):
        self.salt = salt
        self._redis = shared_redis_client
        self._store: dict = {}
        self._salt_manager = salt_manager

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_salt(self) -> bytes:
        if self._salt_manager is not None:
            return self._salt_manager.get_current_salt()
        return self.salt

    def _previous_salt(self) -> Optional[bytes]:
        """Return previous salt only during the 30-day overlap window."""
        if self._salt_manager is not None:
            return self._salt_manager.get_previous_salt()
        return None

    def _make_key(self, hashed_id: str, metric: str) -> str:
        return f"lip:cl_velocity:{hashed_id}:{metric}"

    def _get_value(self, key: str, default):
        if self._redis:
            val = self._redis.get(key)
            if val is None:
                return default
            return val.decode() if isinstance(val, bytes) else val
        return self._store.get(key, default)

    # ── Public interface ──────────────────────────────────────────────────────

    @staticmethod
    def _cents_to_decimal(cents_str: str) -> Decimal:
        """Convert an integer cents string to a Decimal dollar amount."""
        return Decimal(int(cents_str)) / Decimal("100")

    @staticmethod
    def _decimal_to_cents(amount: Decimal) -> int:
        """Convert a Decimal dollar amount to integer cents (truncates sub-cent fractions)."""
        return int(amount * 100)

    def get_cross_licensee_volume(self, tax_id: str) -> Decimal:
        """Return combined volume across current-salt (and previous-salt during overlap).

        Volume is stored in integer cents (via INCRBY) to avoid INCRBYFLOAT
        floating-point rounding errors on money amounts (B7-05).
        """
        current_hashed = cross_licensee_hash(tax_id, self._current_salt())
        raw = self._get_value(self._make_key(current_hashed, "volume"), "0")
        total = self._cents_to_decimal(str(int(raw)) if raw else "0")

        prev_salt = self._previous_salt()
        if prev_salt is not None:
            prev_hashed = cross_licensee_hash(tax_id, prev_salt)
            if prev_hashed != current_hashed:
                prev_raw = self._get_value(self._make_key(prev_hashed, "volume"), "0")
                prev_total = self._cents_to_decimal(str(int(prev_raw)) if prev_raw else "0")
                # Only add previous-salt data if it hasn't already been migrated
                # into the current-salt key (migrate_overlap_period moves it over).
                total = max(total, prev_total)
                logger.debug(
                    "Overlap read: current_hash=%s…, prev_hash=%s…, total=%s",
                    current_hashed[:8], prev_hashed[:8], total,
                )
        return total

    def get_cross_licensee_count(self, tax_id: str) -> int:
        """Return combined transaction count across current-salt (and previous-salt during overlap)."""
        current_hashed = cross_licensee_hash(tax_id, self._current_salt())
        count = int(self._get_value(self._make_key(current_hashed, "count"), 0))

        prev_salt = self._previous_salt()
        if prev_salt is not None:
            prev_hashed = cross_licensee_hash(tax_id, prev_salt)
            if prev_hashed != current_hashed:
                prev_count = int(
                    self._get_value(self._make_key(prev_hashed, "count"), 0)
                )
                count = max(count, prev_count)
        return count

    def record(self, tax_id: str, amount: Decimal) -> None:
        """Record a transaction for the entity.

        During the salt-rotation overlap window, writes to both the
        current-salt key and the previous-salt key to keep both stores
        consistent throughout the 30-day transition period.
        """
        current_hashed = cross_licensee_hash(tax_id, self._current_salt())
        vol_key = self._make_key(current_hashed, "volume")
        cnt_key = self._make_key(current_hashed, "count")

        prev_salt = self._previous_salt()
        prev_hashed = None
        if prev_salt is not None:
            prev_hashed = cross_licensee_hash(tax_id, prev_salt)
            if prev_hashed == current_hashed:
                prev_hashed = None  # same hash — no need for dual write

        # B7-05: Store amounts in integer cents and use INCRBY (not INCRBYFLOAT)
        # to avoid floating-point rounding errors on money amounts.
        amount_cents = self._decimal_to_cents(amount)
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incrby(vol_key, amount_cents)
            pipe.incr(cnt_key)
            if prev_hashed is not None:
                prev_vol_key = self._make_key(prev_hashed, "volume")
                prev_cnt_key = self._make_key(prev_hashed, "count")
                pipe.incrby(prev_vol_key, amount_cents)
                pipe.incr(prev_cnt_key)
            pipe.execute()
        else:
            # In-memory path also stores cents (integer string) for consistency with Redis path
            self._store[vol_key] = str(int(self._store.get(vol_key, "0")) + amount_cents)
            self._store[cnt_key] = int(self._store.get(cnt_key, 0)) + 1
            if prev_hashed is not None:
                prev_vol_key = self._make_key(prev_hashed, "volume")
                prev_cnt_key = self._make_key(prev_hashed, "count")
                self._store[prev_vol_key] = str(
                    int(self._store.get(prev_vol_key, "0")) + amount_cents
                )
                self._store[prev_cnt_key] = int(self._store.get(prev_cnt_key, 0)) + 1

        logger.debug(
            "Cross-licensee record: hash=%s%s amount=%s",
            current_hashed[:8],
            f" (dual-write prev={prev_hashed[:8]})" if prev_hashed else "",
            amount,
        )

    def migrate_overlap_period(self, tax_ids: list) -> int:
        """Copy previous-salt keys to current-salt keys for a list of entities.

        Call this after a salt rotation to pre-populate current-salt velocity
        data from the previous-salt store, eliminating the need to read both
        salts for known entities.

        Parameters
        ----------
        tax_ids:
            List of raw tax ID strings to migrate.

        Returns
        -------
        int
            Number of entities successfully migrated.
        """
        prev_salt = self._previous_salt()
        if prev_salt is None:
            logger.debug("migrate_overlap_period: not in overlap window, nothing to do.")
            return 0

        migrated = 0
        current_salt = self._current_salt()

        for tax_id in tax_ids:
            prev_hashed = cross_licensee_hash(tax_id, prev_salt)
            current_hashed = cross_licensee_hash(tax_id, current_salt)
            if prev_hashed == current_hashed:
                continue

            prev_vol_key = self._make_key(prev_hashed, "volume")
            prev_cnt_key = self._make_key(prev_hashed, "count")
            cur_vol_key = self._make_key(current_hashed, "volume")
            cur_cnt_key = self._make_key(current_hashed, "count")

            prev_vol = Decimal(self._get_value(prev_vol_key, "0"))
            prev_cnt = int(self._get_value(prev_cnt_key, 0))

            if prev_vol == 0 and prev_cnt == 0:
                continue

            if self._redis:
                pipe = self._redis.pipeline()
                pipe.set(cur_vol_key, str(prev_vol), nx=True)
                pipe.set(cur_cnt_key, str(prev_cnt), nx=True)
                pipe.execute()
            else:
                if cur_vol_key not in self._store:
                    self._store[cur_vol_key] = str(prev_vol)
                if cur_cnt_key not in self._store:
                    self._store[cur_cnt_key] = str(prev_cnt)

            migrated += 1
            logger.debug(
                "Migrated: prev_hash=%s… → cur_hash=%s… vol=%s cnt=%d",
                prev_hashed[:8], current_hashed[:8], prev_vol, prev_cnt,
            )

        logger.info("migrate_overlap_period: %d entities migrated.", migrated)
        return migrated
