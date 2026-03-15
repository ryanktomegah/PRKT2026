"""
business_calendar.py — Jurisdiction-specific business day calendar.
GAP-09: Maturity calculations must use business days, not calendar days.

Supported jurisdictions:
  TARGET2  — ECB interbank settlement (EUR corridors)
  FEDWIRE  — Federal Reserve Fedwire (USD corridors)
  CHAPS    — Bank of England CHAPS (GBP corridors)

Holiday data covers 2026–2027. Production deployments should replace the
static tables with a live holiday calendar API (e.g. ICalendar / OpenHolidays).
"""
from __future__ import annotations

from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Static holiday tables — 2026 and 2027
# ---------------------------------------------------------------------------

_TARGET2_HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 6),   # Easter Monday
    date(2026, 5, 1),   # Labour Day
    date(2026, 12, 25), # Christmas Day
    date(2026, 12, 26), # Boxing Day (Second Christmas Day)
    # 2027
    date(2027, 1, 1),   # New Year's Day
    date(2027, 3, 26),  # Good Friday
    date(2027, 3, 29),  # Easter Monday
    date(2027, 5, 1),   # Labour Day (Saturday → observed 2027-05-03 in some markets)
    date(2027, 12, 25), # Christmas Day (Saturday → no observed day for TARGET2)
    date(2027, 12, 26), # Boxing Day (Sunday → observed 2027-12-27)
    date(2027, 12, 27), # Boxing Day observed
})

_FEDWIRE_HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day (3rd Monday Jan)
    date(2026, 2, 16),  # Presidents' Day (3rd Monday Feb)
    date(2026, 5, 25),  # Memorial Day (last Monday May)
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day observed (Jul 4 is Saturday → Jul 3)
    date(2026, 9, 7),   # Labor Day (1st Monday Sep)
    date(2026, 10, 12), # Columbus Day (2nd Monday Oct)
    date(2026, 11, 11), # Veterans Day (Wednesday)
    date(2026, 11, 26), # Thanksgiving Day (4th Thursday Nov)
    date(2026, 12, 25), # Christmas Day
    # 2027
    date(2027, 1, 1),   # New Year's Day
    date(2027, 1, 18),  # Martin Luther King Jr. Day
    date(2027, 2, 15),  # Presidents' Day
    date(2027, 5, 31),  # Memorial Day
    date(2027, 6, 19),  # Juneteenth (Saturday → observed Jun 18)
    date(2027, 6, 18),  # Juneteenth observed
    date(2027, 7, 5),   # Independence Day observed (Jul 4 is Sunday → Jul 5)
    date(2027, 9, 6),   # Labor Day
    date(2027, 10, 11), # Columbus Day
    date(2027, 11, 11), # Veterans Day (Thursday)
    date(2027, 11, 25), # Thanksgiving Day
    date(2027, 12, 24), # Christmas observed (Dec 25 is Saturday → Dec 24)
})

_CHAPS_HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 6),   # Easter Monday
    date(2026, 5, 4),   # Early May Bank Holiday (1st Monday May)
    date(2026, 5, 25),  # Spring Bank Holiday (last Monday May)
    date(2026, 8, 31),  # Summer Bank Holiday (last Monday Aug)
    date(2026, 12, 25), # Christmas Day
    date(2026, 12, 26), # Boxing Day
    # 2027
    date(2027, 1, 1),   # New Year's Day
    date(2027, 3, 26),  # Good Friday
    date(2027, 3, 29),  # Easter Monday
    date(2027, 5, 3),   # Early May Bank Holiday
    date(2027, 5, 31),  # Spring Bank Holiday
    date(2027, 8, 30),  # Summer Bank Holiday
    date(2027, 12, 27), # Christmas Day observed
    date(2027, 12, 28), # Boxing Day observed
})

_CALENDARS: dict[str, frozenset[date]] = {
    "TARGET2": _TARGET2_HOLIDAYS,
    "FEDWIRE": _FEDWIRE_HOLIDAYS,
    "CHAPS": _CHAPS_HOLIDAYS,
}

_CURRENCY_JURISDICTION: dict[str, str] = {
    "EUR": "TARGET2",
    "USD": "FEDWIRE",
    "GBP": "CHAPS",
    "CAD": "FEDWIRE",   # Approximation: LVTS follows Fedwire calendar
    "CHF": "TARGET2",   # SIC follows TARGET2 calendar
    "SEK": "TARGET2",   # RIX follows TARGET2 calendar
    "DKK": "TARGET2",   # KRONOS follows TARGET2 calendar
    "NOK": "TARGET2",   # NBO follows TARGET2 calendar
}


def currency_to_jurisdiction(currency: str) -> str:
    """Map a payment currency to its settlement jurisdiction calendar.

    Args:
        currency: ISO 4217 currency code (e.g. ``"EUR"``, ``"USD"``, ``"GBP"``).

    Returns:
        Jurisdiction string (``"TARGET2"``, ``"FEDWIRE"``, or ``"CHAPS"``).
        Defaults to ``"TARGET2"`` for unrecognised currencies.
    """
    return _CURRENCY_JURISDICTION.get(currency.upper(), "TARGET2")


def is_business_day(d: date, jurisdiction: str = "TARGET2") -> bool:
    """Return True when ``d`` is a business day for the given jurisdiction.

    A business day is a weekday (Mon–Fri) that does not fall on a public
    holiday in the specified settlement calendar.

    Args:
        d: The date to test.
        jurisdiction: Settlement calendar — ``"TARGET2"``, ``"FEDWIRE"``, or
            ``"CHAPS"``.  Defaults to ``"TARGET2"``.

    Returns:
        ``True`` if ``d`` is a business day, ``False`` otherwise.
    """
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    calendar = _CALENDARS.get(jurisdiction, _TARGET2_HOLIDAYS)
    return d not in calendar


def add_business_days(start: date, n: int, jurisdiction: str = "TARGET2") -> date:
    """Advance ``start`` by ``n`` business days in the given jurisdiction.

    Args:
        start: Starting date (inclusive day 0; the first business day counted
            is the day *after* start).
        n: Number of business days to add.  Must be ≥ 0.
        jurisdiction: Settlement calendar — ``"TARGET2"``, ``"FEDWIRE"``, or
            ``"CHAPS"``.  Defaults to ``"TARGET2"``.

    Returns:
        The date ``n`` business days after ``start``.

    Raises:
        ValueError: If ``n`` is negative or if the algorithm cannot find
            enough business days within 365 iterations (calendar table gap).
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    current = start
    remaining = n
    iterations = 0
    while remaining > 0:
        current += timedelta(days=1)
        iterations += 1
        if iterations > 365:
            raise ValueError(
                f"Could not find {n} business days from {start} within 365 days. "
                "Extend the holiday calendar table."
            )
        if is_business_day(current, jurisdiction):
            remaining -= 1
    return current
