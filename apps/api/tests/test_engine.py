"""Fixture regression for the x-iztro adapter (PLAN Phase 3).

Expected values captured from x-iztro 0.6.1 for a known input:
1990-06-15 14:30 male → 命宫 Mậu Dần Thất Sát, 身宫 cư Tài Bạch (index 8),
Thổ ngũ cục, Canh year mutagens Kỵ/Quyền/Lộc/Khoa.
"""

from datetime import date, datetime

import pytest

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.infrastructure.xiztro.engine import XiztroEngine


@pytest.fixture()
def birth() -> NormalizedBirthMoment:
    return NormalizedBirthMoment(
        civilDateTime=datetime(1990, 6, 15, 14, 30),
        normalizedDateTime=datetime(1990, 6, 15, 14, 18),
        gender="male",
        timezoneOffsetMinutes=420,
        correctedSolarDate=date(1990, 6, 15),
        timeIndex=4,
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="test",
        resolvedOffsetMinutes=420,
        normalizationMode="true-solar",
    )


@pytest.fixture()
def profile() -> EngineProfile:
    return EngineProfile(id="iztro-default-v1", engineVersion="0.6.1")


@pytest.fixture(scope="module")
def engine() -> XiztroEngine:
    return XiztroEngine()


def test_cast_chart_fixture(
    birth: NormalizedBirthMoment, profile: EngineProfile, engine: XiztroEngine
) -> None:
    dto = engine.cast_chart(birth, profile)

    assert "config" not in dto.chart
    assert dto.meta["engineVersion"] == "0.6.1"
    assert dto.meta["engineProfileId"] == "iztro-default-v1"

    palaces = dto.chart["palaces"]
    assert len(palaces) == 12

    soul = next(p for p in palaces if p["nameKey"] == "soulPalace")
    assert soul["index"] == 0
    assert soul["heavenlyStem"] == "Mậu" and soul["earthlyBranch"] == "Dần"
    assert [s["key"] for s in soul["majorStars"]] == ["qishaMaj"]

    body = next(p for p in palaces if p["isBodyPalace"])
    assert body["nameKey"] == "wealthPalace" and body["index"] == 8

    assert dto.chart["fiveElementsClassKey"] == "earth5th"
    assert dto.chart["sign"] == "Cung Song Tử"

    mutagens = {
        s["key"]: s["mutagen"]
        for p in palaces
        for s in p["majorStars"]
        if s["mutagen"]
    }
    assert mutagens == {
        "tiantongMaj": "Kỵ",
        "wuquMaj": "Quyền",
        "taiyangMaj": "Lộc",
        "taiyinMaj": "Khoa",
    }

    pattern_keys = {p["key"] for p in dto.chart["patterns"]}
    assert "sha_po_lang" in pattern_keys


def test_get_horoscope(
    birth: NormalizedBirthMoment, profile: EngineProfile, engine: XiztroEngine
) -> None:
    ctx = engine.get_horoscope(birth, profile, date(2026, 3, 1))
    for scope in ("age", "daily", "decadal", "hourly", "monthly", "yearly"):
        assert scope in ctx.context
    assert "lunarDate" in ctx.context


def test_get_surrounded_context(
    birth: NormalizedBirthMoment, profile: EngineProfile, engine: XiztroEngine
) -> None:
    ctx = engine.get_surrounded_context(birth, profile, "soulPalace")
    assert ctx.palaceKey == "soulPalace"
    assert set(ctx.context) == {"target", "career", "wealth", "opposite"}
    assert ctx.context["target"]["nameKey"] == "soulPalace"
    # 三方四正 of 命宫 at index 0: 官禄(4), 财帛(8), 对宫(6)
    assert ctx.context["career"]["index"] == 4
    assert ctx.context["wealth"]["index"] == 8
    assert ctx.context["opposite"]["index"] == 6


def test_unknown_palace_key(
    birth: NormalizedBirthMoment, profile: EngineProfile, engine: XiztroEngine
) -> None:
    with pytest.raises(KeyError):
        engine.get_surrounded_context(birth, profile, "notAKey")
