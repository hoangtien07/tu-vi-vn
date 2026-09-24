from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.birth.contracts import NormalizedBirthMoment, RawBirthInput


def test_raw_input_requires_time() -> None:
    with pytest.raises(ValidationError, match="time is required"):
        RawBirthInput(date=date(1990, 6, 15), gender="male")


def test_raw_input_time_unknown_ok() -> None:
    raw = RawBirthInput(date=date(1990, 6, 15), gender="male", timeUnknown=True)
    assert raw.time is None


def test_normalized_time_index_bounds() -> None:
    kwargs = dict(
        civilDateTime="1990-06-15T14:30:00",
        normalizedDateTime="1990-06-15T14:30:00",
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=date(1990, 6, 15),
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="test",
        resolvedOffsetMinutes=420,
        normalizationMode="civil",
    )
    NormalizedBirthMoment(timeIndex=0, **kwargs)  # type: ignore[arg-type]
    NormalizedBirthMoment(timeIndex=12, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NormalizedBirthMoment(timeIndex=13, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NormalizedBirthMoment(timeIndex=-1, **kwargs)  # type: ignore[arg-type]
