from datetime import date
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.domain.birth.contracts import NormalizedBirthMoment

DTO_SCHEMA_VERSION = 1


class EngineProfile(BaseModel):
    """Engine config as data (SPEC §3). Every chart pins the profile that made it."""

    id: str
    engine: Literal["x-iztro"] = "x-iztro"
    engineVersion: str
    fixLeap: bool = True
    yearDivide: Literal["normal", "exact"] = "normal"
    horoscopeDivide: Literal["normal", "exact"] = "normal"
    ageDivide: Literal["normal", "birthday"] = "normal"
    dayDivide: Literal["forward", "current"] = "forward"
    algorithm: Literal["default", "zhongzhou"] = "default"
    astroType: Literal["heaven", "earth", "human"] = "heaven"
    mutagenTableVersion: str = "builtin"
    brightnessTableVersion: str = "builtin"


class CanonicalChartDTO(BaseModel):
    """Our DTO, not raw engine output (SPEC §6).

    `chart` is the x-iztro to_dict() payload minus `config` — all entities
    addressed by `*_key` (language-independent, I8). schemaVersion lets the
    FE and chartHash track DTO shape.
    """

    schemaVersion: int = DTO_SCHEMA_VERSION
    meta: dict[str, Any]
    chart: dict[str, Any]


class HoroscopeContext(BaseModel):
    targetDate: date
    context: dict[str, Any]


class DomainContext(BaseModel):
    palaceKey: str
    context: dict[str, Any]


class ZiweiEngine(Protocol):
    def cast_chart(
        self, birth: NormalizedBirthMoment, profile: EngineProfile
    ) -> CanonicalChartDTO: ...

    def get_horoscope(
        self, birth: NormalizedBirthMoment, profile: EngineProfile, target: date
    ) -> HoroscopeContext: ...

    def get_surrounded_context(
        self, birth: NormalizedBirthMoment, profile: EngineProfile, palace_key: str
    ) -> DomainContext: ...
