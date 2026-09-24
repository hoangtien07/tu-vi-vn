import dataclasses
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from x_iztro import (
    AgeDivide,
    Algorithm,
    Astro,
    Astrolabe,
    AstroType,
    ChartConfig,
    DayDivide,
    HoroscopeDivide,
    YearDivide,
)

if TYPE_CHECKING:
    from x_iztro.astro import LanguageType, TimeIndexType

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import (
    CanonicalChartDTO,
    DomainContext,
    EngineProfile,
    HoroscopeContext,
)

ENGINE_VERSION = "0.6.1"
CHART_LANGUAGE = "vi-VN"

_DAY_DIVIDE = {"forward": DayDivide.FORWARD, "current": DayDivide.CURRENT}
_YEAR_DIVIDE = {"normal": YearDivide.NORMAL, "exact": YearDivide.EXACT}
_HOROSCOPE_DIVIDE = {"normal": HoroscopeDivide.NORMAL, "exact": HoroscopeDivide.EXACT}
_AGE_DIVIDE = {"normal": AgeDivide.NORMAL, "birthday": AgeDivide.BIRTHDAY}
_ALGORITHM = {"default": Algorithm.DEFAULT, "zhongzhou": Algorithm.ZHONGZHOU}
_ASTRO_TYPE = {"heaven": AstroType.HEAVEN, "earth": AstroType.EARTH, "human": AstroType.HUMAN}


def build_chart_config(profile: EngineProfile) -> ChartConfig:
    """Rebuild ChartConfig from the persisted profile (SPEC §3 hard rule).

    Never rehydrate from chart.to_dict()['config'] — x-iztro drops custom
    mutagens/brightness on serialize → silent revert to defaults.
    """
    return ChartConfig(
        year_divide=_YEAR_DIVIDE[profile.yearDivide],
        horoscope_divide=_HOROSCOPE_DIVIDE[profile.horoscopeDivide],
        age_divide=_AGE_DIVIDE[profile.ageDivide],
        day_divide=_DAY_DIVIDE[profile.dayDivide],
        algorithm=_ALGORITHM[profile.algorithm],
        astro_type=_ASTRO_TYPE[profile.astroType],
    )


def to_canonical(chart: Astrolabe, profile: EngineProfile) -> CanonicalChartDTO:
    """Engine output → CanonicalChartDTO. `config` is dropped (see build_chart_config)."""
    chart_dict: dict[str, Any] = chart.to_dict()
    chart_dict.pop("config", None)
    chart_dict["patterns"] = [
        {k: v for k, v in dataclasses.asdict(p).items() if not k.startswith("_")}
        for p in chart.patterns()
    ]
    return CanonicalChartDTO(
        meta={
            "engine": profile.engine,
            "engineVersion": profile.engineVersion,
            "engineProfileId": profile.id,
            "language": CHART_LANGUAGE,
        },
        chart=chart_dict,
    )


class XiztroEngine:
    """Sole import site for x_iztro (CI import-lint enforces)."""

    def __init__(self) -> None:
        self._astro = Astro()

    def _cast(self, birth: NormalizedBirthMoment, profile: EngineProfile) -> Astrolabe:
        return self._astro.by_solar(
            birth.correctedSolarDate.isoformat(),
            cast("TimeIndexType", birth.timeIndex),
            birth.gender,
            fix_leap=profile.fixLeap,
            language=cast("LanguageType", CHART_LANGUAGE),
            config=build_chart_config(profile),
        )

    def cast_chart(
        self, birth: NormalizedBirthMoment, profile: EngineProfile
    ) -> CanonicalChartDTO:
        return to_canonical(self._cast(birth, profile), profile)

    def get_horoscope(
        self, birth: NormalizedBirthMoment, profile: EngineProfile, target: date
    ) -> HoroscopeContext:
        horoscope = self._cast(birth, profile).horoscope(target.isoformat())
        context: dict[str, Any] = horoscope.to_dict()
        return HoroscopeContext(targetDate=target, context=context)

    def get_surrounded_context(
        self, birth: NormalizedBirthMoment, profile: EngineProfile, palace_key: str
    ) -> DomainContext:
        chart = self._cast(birth, profile)
        palaces = chart.to_dict()["palaces"]
        index = next(
            (p["index"] for p in palaces if p["nameKey"] == palace_key),
            None,
        )
        if index is None:
            raise KeyError(f"unknown palace key: {palace_key}")
        surrounded = chart.surrounded_palaces(index)
        if surrounded is None:
            raise KeyError(f"no surrounded palaces for key: {palace_key}")
        context = {
            "target": palaces[surrounded.target.index],
            "career": palaces[surrounded.career.index],
            "wealth": palaces[surrounded.wealth.index],
            "opposite": palaces[surrounded.opposite.index],
        }
        return DomainContext(palaceKey=palace_key, context=context)
