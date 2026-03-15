"""
test_gap09_business_calendar.py — Tests for GAP-09:
Business-day maturity calculations (TARGET2 / FEDWIRE / CHAPS).
"""
from datetime import date

import pytest

from lip.common.business_calendar import (
    add_business_days,
    currency_to_jurisdiction,
    is_business_day,
)


class TestCurrencyToJurisdiction:
    def test_eur_maps_to_target2(self):
        assert currency_to_jurisdiction("EUR") == "TARGET2"

    def test_usd_maps_to_fedwire(self):
        assert currency_to_jurisdiction("USD") == "FEDWIRE"

    def test_gbp_maps_to_chaps(self):
        assert currency_to_jurisdiction("GBP") == "CHAPS"

    def test_unknown_currency_defaults_to_target2(self):
        assert currency_to_jurisdiction("XYZ") == "TARGET2"


class TestIsBusinessDay:
    def test_saturday_is_not_business_day(self):
        """Apr 4, 2026 is a Saturday."""
        assert not is_business_day(date(2026, 4, 4), "TARGET2")

    def test_sunday_is_not_business_day(self):
        """Apr 5, 2026 is a Sunday."""
        assert not is_business_day(date(2026, 4, 5), "TARGET2")

    def test_good_friday_not_business_day_target2(self):
        """Good Friday Apr 3, 2026 is a TARGET2 holiday."""
        assert not is_business_day(date(2026, 4, 3), "TARGET2")

    def test_good_friday_not_business_day_chaps(self):
        """Good Friday Apr 3, 2026 is also a CHAPS holiday."""
        assert not is_business_day(date(2026, 4, 3), "CHAPS")

    def test_regular_monday_is_business_day(self):
        """Apr 7, 2026 is Easter Monday — holiday for TARGET2/CHAPS."""
        assert not is_business_day(date(2026, 4, 6), "TARGET2")
        # But Apr 7 (Tuesday after Easter) is a business day
        assert is_business_day(date(2026, 4, 7), "TARGET2")

    def test_may_day_not_business_day_target2(self):
        """May 1, 2026 is a TARGET2 holiday (Labour Day)."""
        assert not is_business_day(date(2026, 5, 1), "TARGET2")

    def test_may_day_is_business_day_fedwire(self):
        """May 1, 2026 is NOT a Fedwire holiday."""
        assert is_business_day(date(2026, 5, 1), "FEDWIRE")


class TestAddBusinessDays:
    def test_3_business_days_skips_weekend(self):
        """Friday + 3 business days = Wednesday (skipping Sat/Sun)."""
        friday = date(2026, 3, 27)  # Regular Friday
        result = add_business_days(friday, 3, "TARGET2")
        # Sat Mar 28 + Sun Mar 29 skipped → Mon 30, Tue 31, Wed Apr 1
        assert result == date(2026, 4, 1)

    def test_7_business_days_from_friday(self):
        """7 business days from Friday = next-next Monday."""
        friday = date(2026, 3, 27)
        result = add_business_days(friday, 7, "TARGET2")
        # Skipping 2 weekends: Mon30,Tue31,Wed1,Thu2,Fri3(GoodFri-skip),Mon6(EasterMon-skip),Tue7,Wed8
        # Mar 30, 31, Apr 1, 2 = 4 days; Apr 3 is Good Friday (skip), Apr 6 Easter Monday (skip)
        # Apr 7 = 5, Apr 8 = 6, Apr 9 = 7
        assert result == date(2026, 4, 9)

    def test_zero_business_days(self):
        """0 business days returns the start date unchanged."""
        monday = date(2026, 3, 30)
        assert add_business_days(monday, 0, "TARGET2") == monday

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            add_business_days(date(2026, 1, 5), -1)

    def test_fedwire_skips_mlk_day(self):
        """MLK Day Jan 19, 2026 is a Fedwire holiday."""
        # Start Friday Jan 16 — 1 business day should skip weekend AND MLK Day
        fri = date(2026, 1, 16)
        result = add_business_days(fri, 1, "FEDWIRE")
        # Sat Jan 17, Sun Jan 18, Mon Jan 19 (MLK) all skipped → Tue Jan 20
        assert result == date(2026, 1, 20)

    def test_class_a_3bd_from_friday_not_monday(self):
        """Core GAP-09 scenario: Class A maturity must NOT land on Monday 17:00."""
        fri = date(2026, 4, 24)  # Regular Friday
        result = add_business_days(fri, 3, "TARGET2")
        # Should be Wed Apr 29, NOT Mon Apr 27 (calendar day Fri+3)
        assert result == date(2026, 4, 29)
        assert result.weekday() == 2  # Wednesday
