"""Lunar→solar conversion + lunar-input validation via the engine's own tables.

Using x-iztro for conversion keeps the calendar consistent with the cast —
converter version is the engine version (CALENDAR_CONVERTER_VERSION).
"""

import datetime as dt

from x_iztro import Astro

from app.domain.birth.normalizer import CALENDAR_CONVERTER_VERSION


class InvalidLunarDateError(ValueError):
    pass


class NotLeapMonthError(ValueError):
    pass


def _solar_of(astro: Astro, lunar: dt.date, is_leap: bool) -> dt.date:
    try:
        chart = astro.by_lunar(
            f"{lunar.year}-{lunar.month}-{lunar.day}",
            0,
            "male",
            is_leap_month=is_leap,
            fix_leap=True,
        )
    except Exception as exc:  # engine wraps lunar errors as IztroError
        raise InvalidLunarDateError(str(exc)) from exc
    return dt.datetime.strptime(chart.to_dict()["solarDate"], "%Y-%m-%d").date()


def lunar_month_is_leap(astro: Astro, year: int, month: int) -> bool:
    """Month M of lunar year Y has a leap month iff requesting the leap variant
    changes the solar result (engine silently ignores is_leap on non-leap months)."""
    first = dt.date(year, month, 1)
    return _solar_of(astro, first, True) != _solar_of(astro, first, False)


def lunar_to_solar(lunar: dt.date, is_leap_month: bool) -> dt.date:
    astro = Astro()
    if is_leap_month and not lunar_month_is_leap(astro, lunar.year, lunar.month):
        raise NotLeapMonthError(
            f"lunar month {lunar.year}-{lunar.month} is not a leap month"
        )
    return _solar_of(astro, lunar, is_leap_month)


CONVERTER_VERSION = CALENDAR_CONVERTER_VERSION
