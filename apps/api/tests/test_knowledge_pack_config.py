"""SPEC_V04 I17 — explicit knowledge pack selection (builtin|none|path)."""

import json

import pytest

from app.infrastructure.xiztro.knowledge import KnowledgeRegistry


@pytest.fixture(autouse=True)
def _restore_pack():
    yield
    KnowledgeRegistry.configure("builtin")


def _pack_dict() -> dict:
    return {
        "id": "vn-seed-test",
        "version": "1",
        "language": "vi-VN",
        "source": {"url": "test", "commit": "", "license": "MIT"},
        "schema": 1,
        "stars": {
            "taiyangMaj": {
                "key": "taiyangMaj",
                "name": "Thái Dương",
                "category": "major",
                "intro": "Sao Thái Dương — quang quý, nhiệt huyết.",
            }
        },
        "palaces": {
            "soulPalace": {
                "key": "soulPalace",
                "name": "Mệnh",
                "intro": "Cung Mệnh — nền tảng bản mệnh.",
            }
        },
        "patterns": {},
        "mutagens": {},
        "concepts": {},
        "extends": None,
    }


def test_none_ablation_returns_no_excerpts() -> None:
    KnowledgeRegistry.configure("none")
    assert KnowledgeRegistry.star_excerpt("taiyangMaj") is None
    assert KnowledgeRegistry.palace_excerpt("soulPalace") is None
    assert KnowledgeRegistry.pattern_excerpt("x") is None
    assert KnowledgeRegistry.version_info()["id"] == "none"


def test_builtin_still_default() -> None:
    KnowledgeRegistry.configure("builtin")
    info = KnowledgeRegistry.version_info()
    assert info["language"] == "zh-CN"
    assert info["id"] != "none"


def test_file_pack_from_dict(tmp_path) -> None:
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(_pack_dict()))
    KnowledgeRegistry.configure(str(p))
    star = KnowledgeRegistry.star_excerpt("taiyangMaj")
    assert star is not None and star["name"] == "Thái Dương"
    palace = KnowledgeRegistry.palace_excerpt("soulPalace")
    assert palace is not None and palace["name"] == "Mệnh"
    info = KnowledgeRegistry.version_info()
    assert info["id"] == "vn-seed-test" and info["language"] == "vi-VN"


def test_missing_file_pack_fails_loud(tmp_path) -> None:
    KnowledgeRegistry.configure(str(tmp_path / "nope.json"))
    with pytest.raises((OSError, Exception)):
        KnowledgeRegistry.active_pack()
