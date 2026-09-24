from datetime import date, datetime

import pytest

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import EngineProfile
from app.domain.context.composer import ContextComposer
from app.domain.evidence.builder import EvidenceBuilder
from app.infrastructure.xiztro.engine import XiztroEngine
from app.infrastructure.xiztro.knowledge import KnowledgeRegistry


@pytest.fixture(scope="module")
def engine() -> XiztroEngine:
    return XiztroEngine()


@pytest.fixture(scope="module")
def profile() -> EngineProfile:
    return EngineProfile(id="iztro-default-v1", engineVersion="0.6.1")


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def dto(engine, birth, profile):
    return engine.cast_chart(birth, profile)


def test_overview_is_compact_full_chart(engine, birth, profile, dto):
    ctx = ContextComposer(engine).compose(birth, profile, dto, "overview")
    kinds = {i.kind for i in ctx.items}
    assert "chart_fact" in kinds and "pattern" in kinds
    astrolabe = next(i for i in ctx.items if i.entity_key == "astrolabe")
    assert len(astrolabe.data["palaces"]) == 12


def test_career_selective(engine, birth, profile, dto):
    ctx = ContextComposer(engine).compose(birth, profile, dto, "career")
    palace_items = [i for i in ctx.items if i.kind == "palace_fact"]
    keys = {i.palace_key for i in palace_items}
    # main palace + 三方四正 (career/wealth/opposite roles)
    assert "careerPalace" in keys and len(palace_items) == 4
    # not the whole chart
    assert all(i.kind != "chart_fact" for i in ctx.items)


def test_career_with_year_target(engine, birth, profile, dto):
    ctx = ContextComposer(engine).compose(
        birth, profile, dto, "career", target_date=date(2028, 3, 1)
    )
    expected = {"decadal", "yearly", "monthly", "daily", "age"}
    assert set(ctx.scopes_included) == expected
    horo = [i for i in ctx.items if i.kind == "horoscope_fact"]
    assert {i.entity_key for i in horo} == expected
    assert all(i.scope.startswith(tuple(expected)) for i in horo)


def test_evidence_bundle_stable_ids(engine, birth, profile, dto):
    composer = ContextComposer(engine)
    builder = EvidenceBuilder(knowledge_version="iztro-docs@x")
    ctx1 = composer.compose(birth, profile, dto, "career")
    ctx2 = composer.compose(birth, profile, dto, "career")
    b1 = builder.build(ctx1, "ev_1")
    b2 = builder.build(ctx2, "ev_2")
    # deterministic: same context → same ID assignment
    assert [i.id for i in b1.items] == [i.id for i in b2.items]
    assert [i.id for i in b1.items] == [f"E{i:03d}" for i in range(1, len(b1.items) + 1)]
    # sorted by (kind, palace_key, entity_key)
    assert b1.items[0].kind == "palace_fact"


def test_evidence_knowledge_marked(engine, birth, profile, dto):
    ctx = ContextComposer(engine).compose(
        birth, profile, dto, "career", knowledge=KnowledgeRegistry
    )
    builder = EvidenceBuilder(knowledge_version="2026-08-19+ec2d58b")
    bundle = builder.build(ctx, "ev_k")
    knowledge_items = [i for i in bundle.items if i.kind == "knowledge"]
    assert knowledge_items
    assert all(i.source == "iztro-docs" for i in knowledge_items)
    assert all(i.source_version == "2026-08-19+ec2d58b" for i in knowledge_items)
    # knowledge follows facts in ordering
    kinds = [i.kind for i in bundle.items]
    assert kinds.index("knowledge") > kinds.index("palace_fact")


def test_vocab_keys(engine, birth, profile, dto):
    ctx = ContextComposer(engine).compose(birth, profile, dto, "career")
    bundle = EvidenceBuilder().build(ctx, "ev_v")
    vocab = EvidenceBuilder.vocab_keys(bundle)
    assert "careerPalace" in vocab and len(vocab) > 3


def test_knowledge_registry() -> None:
    info = KnowledgeRegistry.version_info()
    assert info["id"] == "iztro-docs" and info["language"] == "zh-CN"
    star = KnowledgeRegistry.star_excerpt("ziweiMaj")
    assert star and len(star["excerpt"]) <= 300
    pattern = KnowledgeRegistry.pattern_excerpt("sha_po_lang")
    assert pattern and pattern["name"] == "杀破狼"
