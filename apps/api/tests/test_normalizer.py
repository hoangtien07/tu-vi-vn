import datetime as dt

import pytest

from app.domain.birth.contracts import RawBirthInput
from app.domain.birth.normalizer import (
    SolarCoordinateRequiredError,
    civil_moment,
    equation_of_time_minutes,
    normalize,
    to_iztro_time_index,
)
from app.domain.birth.vn_timezone import BirthRegionRequiredError, resolve_offset_minutes
from app.infrastructure.xiztro.calendar import lunar_to_solar

HCM = dt.timezone(dt.timedelta(hours=7))


def _raw(**kw: object) -> RawBirthInput:
    base: dict[str, object] = dict(
        date=dt.date(1990, 6, 15), time=dt.time(14, 30), gender="male",
        longitude=105.85, trueSolarTimeEnabled=True,
    )
    base.update(kw)
    return RawBirthInput.model_validate(base)


def _normalize(raw: RawBirthInput):
    return normalize(raw, civil_moment(raw, lunar_to_solar))


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(0, 0, 0), (0, 59, 0), (1, 0, 1), (22, 59, 11), (23, 0, 12), (23, 59, 12)],
)
def test_time_index_boundaries(hour: int, minute: int, expected: int) -> None:
    assert to_iztro_time_index(dt.time(hour, minute)) == expected


def test_true_solar_correction() -> None:
    raw = _raw()
    normalized = _normalize(raw)
    # 105.85°E vs 105°E meridian: +3.4 min; EoT mid-June ≈ -0.5..-1 min
    assert normalized.normalizationMode == "true-solar"
    assert normalized.longitudeCorrectionMinutes == pytest.approx(3.4, abs=0.01)
    assert abs(normalized.equationOfTimeMinutes) < 2.0
    assert normalized.correctedSolarDate == dt.date(1990, 6, 15)
    assert normalized.dateShift == 0


def test_modern_default_offset() -> None:
    assert resolve_offset_minutes(dt.datetime(1990, 6, 15), None) == (420, [])


def test_divergence_window_requires_region() -> None:
    with pytest.raises(BirthRegionRequiredError):
        resolve_offset_minutes(dt.datetime(1970, 1, 1, 12), None)
    with pytest.raises(BirthRegionRequiredError):
        resolve_offset_minutes(dt.datetime(1954, 11, 15, 12), None)
    # outside windows no region needed
    assert resolve_offset_minutes(dt.datetime(1976, 1, 1), None)[0] == 420


def test_divergence_window_regions() -> None:
    moment = dt.datetime(1970, 1, 1, 12)
    assert resolve_offset_minutes(moment, "north") == (420, [])
    assert resolve_offset_minutes(moment, "south") == (480, [])
    assert resolve_offset_minutes(moment, "central") == (480, [])


def test_north_october_1954_ambiguous() -> None:
    offset, warnings = resolve_offset_minutes(dt.datetime(1954, 10, 15), "north")
    assert offset == 420
    assert warnings
    assert resolve_offset_minutes(dt.datetime(1954, 9, 15), "north")[0] == 480


def test_south_boundaries() -> None:
    assert resolve_offset_minutes(dt.datetime(1959, 12, 31, 23, 59), "south") == (420, [])
    assert resolve_offset_minutes(dt.datetime(1960, 1, 1), "south") == (480, [])
    assert resolve_offset_minutes(dt.datetime(1975, 6, 12, 22, 59), "south") == (480, [])
    assert resolve_offset_minutes(dt.datetime(1975, 6, 12, 23, 0), "south") == (420, [])


def test_tst_requires_longitude() -> None:
    raw = _raw(longitude=None)
    with pytest.raises(SolarCoordinateRequiredError):
        _normalize(raw)


def test_civil_mode_no_coordinates() -> None:
    normalized = _normalize(_raw(longitude=None, trueSolarTimeEnabled=False))
    assert normalized.normalizationMode == "civil"
    assert normalized.totalSolarCorrectionMinutes == 0


def test_lunar_input_converts() -> None:
    raw = _raw(calendar="lunar", date=dt.date(1990, 5, 23))
    normalized = _normalize(raw)
    assert normalized.correctedSolarDate == dt.date(1990, 6, 15)


def test_lunar_leap_month() -> None:
    civil = civil_moment(
        _raw(calendar="lunar", date=dt.date(2020, 4, 15), leapMonth=True),
        lunar_to_solar,
    )
    assert civil.civilDateTime.date() == dt.date(2020, 6, 6)


def test_lunar_invalid_leap() -> None:
    with pytest.raises(ValueError, match="not a leap month"):
        civil_moment(
            _raw(calendar="lunar", date=dt.date(1990, 6, 1), leapMonth=True),
            lunar_to_solar,
        )


def test_equation_of_time_bounds() -> None:
    assert all(-20 < equation_of_time_minutes(n) < 20 for n in range(1, 366))
