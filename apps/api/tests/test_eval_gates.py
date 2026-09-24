"""Release-gate eval runner (docs/EVALUATION.md Gates A–E).

Cases live in eval/cases/*.json at the repo root. Gates A (normalization),
B-CI (chart regression), C (grounding) and D (topic routing) run here as
pytest; Gate B's JS differential oracle runs nightly (not CI); Gate E is
schema-validated here and scored by the model benchmark harness.
"""

import datetime as dt
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.birth.contracts import NormalizedBirthMoment, RawBirthInput
from app.domain.birth.normalizer import (
    SolarCoordinateRequiredError,
    civil_moment,
    normalize,
)
from app.domain.birth.vn_timezone import BirthRegionRequiredError
from app.domain.chart.contracts import EngineProfile
from app.domain.context.composer import ContextComposer
from app.domain.evidence.builder import EvidenceBundle
from app.domain.interpretation import grounding
from app.infrastructure.xiztro.calendar import (
    InvalidLunarDateError,
    NotLeapMonthError,
    lunar_to_solar,
)
from app.infrastructure.xiztro.engine import XiztroEngine

CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "cases"


def _cases(name: str) -> dict:
    return json.loads((CASES_DIR / name).read_text())


def _domain_errors() -> dict[str, type[Exception]]:
    return {
        "BirthRegionRequiredError": BirthRegionRequiredError,
        "SolarCoordinateRequiredError": SolarCoordinateRequiredError,
        "NotLeapMonthError": NotLeapMonthError,
        "InvalidLunarDateError": InvalidLunarDateError,
    }


class TestGateA:
    """Birth normalization boundary corpus."""

    def test_corpus_size(self) -> None:
        assert len(_cases("birth-normalization.json")["cases"]) >= 20

    @pytest.mark.parametrize(
        "case", _cases("birth-normalization.json")["cases"], ids=lambda c: c["id"]
    )
    def test_case(self, case: dict) -> None:
        expect = case["expect"]
        error = expect.get("error")
        if error == "validation":
            with pytest.raises(ValidationError):
                RawBirthInput(**case["input"])
            return
        raw = RawBirthInput(**case["input"])
        if error:
            with pytest.raises(_domain_errors()[error]):
                normalize(raw, civil_moment(raw, lunar_to_solar))
            return
        moment = normalize(raw, civil_moment(raw, lunar_to_solar))
        if "offset" in expect:
            assert moment.resolvedOffsetMinutes == expect["offset"]
        if "timeIndex" in expect:
            assert moment.timeIndex == expect["timeIndex"]
        if "correctedSolarDate" in expect:
            assert moment.correctedSolarDate.isoformat() == expect["correctedSolarDate"]
        if "provisional" in expect:
            assert moment.provisional is expect["provisional"]
        if "normalizationMode" in expect:
            assert moment.normalizationMode == expect["normalizationMode"]
        if "warningsHas" in expect:
            assert any(expect["warningsHas"] in w for w in moment.warnings)


def _normalized(birth: dict) -> NormalizedBirthMoment:
    corrected = dt.date.fromisoformat(birth["correctedSolarDate"])
    return NormalizedBirthMoment(
        civilDateTime=dt.datetime.combine(corrected, dt.time(12, 0)),
        normalizedDateTime=dt.datetime.combine(corrected, dt.time(12, 0)),
        gender=birth["gender"],
        timezoneOffsetMinutes=420,
        correctedSolarDate=corrected,
        timeIndex=birth["timeIndex"],
        tzKey="Asia/Ho_Chi_Minh",
        tzdataVersion="vn-tst-v1",
        resolvedOffsetMinutes=420,
        normalizationMode="civil",
    )


def _profile(overrides: dict | None) -> EngineProfile:
    return EngineProfile(
        id="iztro-default-v1", engineVersion="0.6.1", **(overrides or {})
    )


class TestGateB:
    """Frozen chart-regression corpus (CI tier of the differential oracle)."""

    engine = XiztroEngine()

    @pytest.mark.parametrize(
        "case", _cases("chart-regression.json")["cases"], ids=lambda c: c["id"]
    )
    def test_case(self, case: dict) -> None:
        dto = self.engine.cast_chart(
            _normalized(case["birth"]), _profile(case.get("profile"))
        )
        expect = case["expect"]
        palaces = dto.chart["palaces"]

        if "soulPalace" in expect:
            soul = next(p for p in palaces if p["nameKey"] == "soulPalace")
            want = expect["soulPalace"]
            assert soul["index"] == want["index"]
            assert soul["heavenlyStem"] == want["stem"]
            assert soul["earthlyBranch"] == want["branch"]
            assert [s["key"] for s in soul["majorStars"]] == want["majorStars"]

        if "bodyPalace" in expect:
            body = next(p for p in palaces if p["isBodyPalace"])
            assert body["nameKey"] == expect["bodyPalace"]["nameKey"]
            assert body["index"] == expect["bodyPalace"]["index"]

        if "fiveElementsClassKey" in expect:
            assert dto.chart["fiveElementsClassKey"] == expect["fiveElementsClassKey"]

        if "mutagens" in expect:
            mutagens = {
                s["key"]: s["mutagen"]
                for p in palaces
                for s in p["majorStars"]
                if s["mutagen"]
            }
            assert mutagens == expect["mutagens"]

        pattern_keys = {p["key"] for p in dto.chart["patterns"]}
        for key in expect.get("patternsPresent", []):
            assert key in pattern_keys
        for key in expect.get("patternsAbsent", []):
            assert key not in pattern_keys


class TestGateC:
    """Grounding zero-tolerance cases."""

    @pytest.mark.parametrize(
        "case", _cases("grounding.json")["cases"], ids=lambda c: c["id"]
    )
    def test_case(self, case: dict) -> None:
        bundle = EvidenceBundle(
            id="eval", topic="eval", items=case["bundle"]["items"]
        )
        result = grounding.validate(case["output"], bundle)
        expect = case["expect"]
        assert result.ok is expect["ok"], result
        for field in expect.get("violations", []):
            assert getattr(result, field), f"{field} should be non-empty"
        if expect.get("orphanClaims"):
            assert result.orphan_claims


class TestGateD:
    """ContextComposer routing cases."""

    engine = XiztroEngine()
    composer = ContextComposer(engine)

    @pytest.mark.parametrize(
        "case", _cases("topic-routing.json")["cases"], ids=lambda c: c["id"]
    )
    def test_case(self, case: dict) -> None:
        birth = _cases("topic-routing.json")["birth"]
        normalized = _normalized(birth)
        profile = _profile(None)
        dto = self.engine.cast_chart(normalized, profile)
        target = dt.date.fromisoformat(case["target"]) if case.get("target") else None

        ctx = self.composer.compose(normalized, profile, dto, case["topic"], target)
        expect = case["expect"]

        if "scopes" in expect:
            assert ctx.scopes_included == expect["scopes"]
        kinds = {i.kind for i in ctx.items}
        for kind in expect.get("requiredKinds", []):
            assert kind in kinds, f"missing required context kind {kind}"
        for kind in expect.get("forbiddenKinds", []):
            assert kind not in kinds, f"unnecessary context kind {kind}"
        if "mainPalace" in expect:
            assert any(
                i.entity_key == expect["mainPalace"] for i in ctx.items
            ), f"missing main palace {expect['mainPalace']}"


class TestGateE:
    """Schema + coverage of the interpretation-quality corpus.

    Scoring runs in the model benchmark harness — this gate guarantees the
    corpus is well-formed and covers the required scenario types.
    """

    def test_corpus(self) -> None:
        cases = _cases("interpretation.json")["cases"]
        types = {c["type"] for c in cases}
        assert {"rubric", "safety-bait", "injection-bait"} <= types
        assert len(cases) >= 8
        for case in cases:
            assert case.get("prompt") or case.get("chat"), case["id"]
            assert "rubric" in case, case["id"]
            if case["type"] != "rubric":
                assert case["autoFail"], case["id"]
