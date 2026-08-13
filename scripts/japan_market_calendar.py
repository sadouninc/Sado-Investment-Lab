from __future__ import annotations

from datetime import date, timedelta
import math


def _nth_monday(year: int, month: int, nth: int) -> date:
    first = date(year, month, 1)
    offset = (7 - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (nth - 1))


def _vernal_equinox_day(year: int) -> int:
    return math.floor(20.8431 + 0.242194 * (year - 1980) - math.floor((year - 1980) / 4))


def _autumn_equinox_day(year: int) -> int:
    return math.floor(23.2488 + 0.242194 * (year - 1980) - math.floor((year - 1980) / 4))


def _base_public_holidays(year: int) -> set[date]:
    if not 2022 <= year <= 2099:
        raise ValueError("Japan market calendar supports years 2022..2099")
    return {
        date(year, 1, 1),
        _nth_monday(year, 1, 2),
        date(year, 2, 11),
        date(year, 2, 23),
        date(year, 3, _vernal_equinox_day(year)),
        date(year, 4, 29),
        date(year, 5, 3),
        date(year, 5, 4),
        date(year, 5, 5),
        _nth_monday(year, 7, 3),
        date(year, 8, 11),
        _nth_monday(year, 9, 3),
        date(year, 9, _autumn_equinox_day(year)),
        _nth_monday(year, 10, 2),
        date(year, 11, 3),
        date(year, 11, 23),
    }


def japan_public_holidays(year: int) -> set[date]:
    """Return deterministic national holidays, including substitute/citizens holidays.

    The implementation is intentionally bounded to the modern rule set used by the
    Investment OS. Years outside 2022..2099 fail closed instead of being guessed.
    """
    holidays = _base_public_holidays(year)

    # Citizens' Holiday: a weekday between two national holidays becomes a holiday.
    cursor = date(year, 1, 2)
    end = date(year, 12, 30)
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            if cursor - timedelta(days=1) in holidays and cursor + timedelta(days=1) in holidays:
                holidays.add(cursor)
        cursor += timedelta(days=1)

    # Substitute holiday: when a national holiday falls on Sunday, the next
    # non-holiday weekday is closed.
    for holiday in sorted(tuple(holidays)):
        if holiday.weekday() != 6:
            continue
        substitute = holiday + timedelta(days=1)
        while substitute in holidays:
            substitute += timedelta(days=1)
        holidays.add(substitute)

    return holidays


def is_japan_market_business_day(day: date) -> bool:
    """Return whether JP equities should be treated as a normal trading business day.

    JPX year-end closures are added to national holidays. Unsupported calendar years
    raise rather than silently treating an unknown date as open.
    """
    if day.weekday() >= 5:
        return False
    if day in {date(day.year, 1, 2), date(day.year, 1, 3), date(day.year, 12, 31)}:
        return False
    return day not in japan_public_holidays(day.year)
