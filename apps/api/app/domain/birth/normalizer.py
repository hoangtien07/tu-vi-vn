"""BirthTimeNormalizer — civil birth moment → engine-ready moment (SPEC §5).

CivilBirthMoment
  → VN tz rule table (region-aware) → longitude correction
  → equation of time → date rollover
  → NormalizedBirthMoment (correctedSolarDate, timeIndex 0–12)

Late Tý (23:00–24:00) ownership: the normalizer emits the corrected date and
time index verbatim — the day roll is owned exclusively by EngineProfile.dayDivide.
"""

import datetime as dt
import math
from collections.abc import Callable

from app.domain.birth.contracts import (
    NORMALIZER_VERSION,
    CivilBirthMoment,
    NormalizedBirthMoment,
    RawBirthInput,
)
from app.domain.birth.vn_timezone import VN_TZ_VERSION, resolve_offset_minutes

CALENDAR_CONVERTER_VERSION = "x-iztro-0.6.1"

# (date, is_leap_month) -> solar date; injected from infrastructure/xiztro.
LunarToSolar = Callable[[dt.date, bool], dt.date]

class SolarCoordinateRequiredError(ValueError):
    pass


def equation_of_time_minutes(day_of_year: int) -> float:
    """NOAA approximation (minutes)."""
    b = math.radians(360.0 / 365.0 * (day_of_year - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def to_iztro_time_index(t: dt.time) -> int:
    """0 = Tý sớm (00–01h), 1–11 = 2-hour branches, 12 = Tý muộn (23–24h)."""
    return 12 if t.hour == 23 else (t.hour + 1) // 2


def civil_moment(raw: RawBirthInput, lunar_to_solar: LunarToSolar) -> CivilBirthMoment:
    """RawBirthInput → CivilBirthMoment (solar calendar, civil wall clock)."""
    source_calendar = raw.calendar
    solar_date = raw.date
    if raw.calendar == "lunar":
        solar_date = lunar_to_solar(raw.date, raw.leapMonth)
    civil_dt = dt.datetime.combine(solar_date, raw.time or dt.time(12, 0))
    return CivilBirthMoment(
        civilDateTime=civil_dt,
        timezone=raw.timezone,
        latitude=raw.latitude,
        longitude=raw.longitude,
        sourceCalendar=source_calendar,
        calendarConverterVersion=CALENDAR_CONVERTER_VERSION,
    )


def normalize(
    raw: RawBirthInput, civil: CivilBirthMoment
) -> NormalizedBirthMoment:
    local_dt = civil.civilDateTime
    offset_minutes, warnings = resolve_offset_minutes(local_dt, raw.birthRegion)

    longitude_correction = 0.0
    eot = 0.0
    solar_enabled = raw.trueSolarTimeEnabled
    if solar_enabled:
        if civil.longitude is None:
            raise SolarCoordinateRequiredError(
                "trueSolarTimeEnabled requires longitude"
            )
        standard_meridian = offset_minutes / 60.0 * 15.0
        longitude_correction = (civil.longitude - standard_meridian) * 4.0
        eot = equation_of_time_minutes(local_dt.timetuple().tm_yday)

    total = longitude_correction + eot
    normalized_dt = local_dt + dt.timedelta(minutes=total)
    corrected_date = normalized_dt.date()
    date_shift = (corrected_date - local_dt.date()).days

    return NormalizedBirthMoment(
        civilDateTime=local_dt,
        normalizedDateTime=normalized_dt,
        gender=raw.gender,
        timezoneOffsetMinutes=offset_minutes,
        dstCorrectionMinutes=0,
        longitudeCorrectionMinutes=longitude_correction,
        equationOfTimeMinutes=eot,
        totalSolarCorrectionMinutes=total,
        dateShift=date_shift,
        correctedSolarDate=corrected_date,
        timeIndex=to_iztro_time_index(normalized_dt.time()),
        tzKey=raw.timezone,
        tzdataVersion=VN_TZ_VERSION,
        resolvedOffsetMinutes=offset_minutes,
        normalizationMode="true-solar" if solar_enabled else "civil",
        normalizerVersion=NORMALIZER_VERSION,
        warnings=warnings,
    )
