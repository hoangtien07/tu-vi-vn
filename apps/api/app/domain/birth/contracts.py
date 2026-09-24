import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Gender = Literal["male", "female"]
BirthRegion = Literal["north", "central", "south"]

NORMALIZER_VERSION = "vn-tst-v1"


class RawBirthInput(BaseModel):
    """User input verbatim — audit trail, never overwritten (SPEC §4.1)."""

    calendar: Literal["solar", "lunar"] = "solar"
    date: dt.date
    time: dt.time | None = None
    timeUnknown: bool = False
    gender: Gender
    placeName: str | None = None
    birthRegion: BirthRegion | None = None
    timezone: str = "Asia/Ho_Chi_Minh"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    leapMonth: bool = False
    trueSolarTimeEnabled: bool = True

    @model_validator(mode="after")
    def time_required_unless_unknown(self) -> "RawBirthInput":
        if not self.timeUnknown and self.time is None:
            raise ValueError("time is required when timeUnknown is false")
        return self


class CivilBirthMoment(BaseModel):
    """Gregorian civil datetime after calendar conversion (SPEC §4.2)."""

    civilDateTime: dt.datetime
    timezone: str
    latitude: float | None = None
    longitude: float | None = None
    sourceCalendar: Literal["solar", "lunar"]
    calendarConverterVersion: str


class NormalizedBirthMoment(BaseModel):
    """After BirthTimeNormalizer — engine input is (correctedSolarDate, timeIndex).

    timeIndex has 13 slots 0–12 (0 = Tý sớm 00–01h, 12 = Tý muộn 23–24h).
    Day roll is owned exclusively by EngineProfile.dayDivide (SPEC §5).
    """

    civilDateTime: dt.datetime
    normalizedDateTime: dt.datetime
    gender: Gender
    timezoneOffsetMinutes: int
    dstCorrectionMinutes: int = 0
    longitudeCorrectionMinutes: float = 0
    equationOfTimeMinutes: float = 0
    totalSolarCorrectionMinutes: float = 0
    dateShift: int = 0
    correctedSolarDate: dt.date
    timeIndex: int = Field(ge=0, le=12)
    tzKey: str
    tzdataVersion: str
    resolvedOffsetMinutes: int
    normalizationMode: Literal["civil", "true-solar"]
    normalizerVersion: str = NORMALIZER_VERSION
