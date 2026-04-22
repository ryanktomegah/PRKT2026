"""
offer_delivery_race_fix.py — Minimal race condition fix (ESG-02).

ESG-02: ELO accept() and background expire_stale_offers() can race.
- ELO sees offer in PENDING state and calls accept()
- Simultaneously, background sweeper sees offer in PENDING state and moves it to EXPIRED
- Both check "is offer in PENDING" simultaneously
- Winner moves state, loser gets "offer not found" or "already resolved"

Fix: Add 5-second grace period to offers - ELO acceptance wins
within grace period, sweeper skips expiry.
"""
from datetime import datetime, timedelta, timezone

OFFER_GRACE_PERIOD_SECONDS = 5
_OFFER_STATE_KEY_PREFIX = "lip:offer:race_fixed:"


def add_grace_period(offer_expiry: datetime) -> datetime:
    """Add grace period to offer expiry time."""
    return offer_expiry + timedelta(seconds=OFFER_GRACE_PERIOD_SECONDS)


def is_within_grace_period(offer_expiry: datetime, now: datetime = None) -> bool:
    """Check if current time is within grace period of offer expiry."""
    now = now or datetime.now(tz=timezone.utc)
    grace_end = add_grace_period(offer_expiry)
    return now < grace_end
