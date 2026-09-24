"""PromptRenderer — topic + ComposedContext + EvidenceBundle → messages[].

Prompt files live in app/prompts/ (SPEC §15); the sha256 of their concatenated
content is the prompt-template version recorded on every InterpretationRun.
"""

import hashlib
import json
from pathlib import Path

from app.domain.evidence.builder import EvidenceBundle

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
GLOSSARY_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "knowledge" / "glossary-vi.md"
)
PROMPT_VERSION_SUFFIX = "v1"

_FILES = ("system.md", "evidence-policy.md", "output-vi.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def template_sha256(topic: str) -> str:
    h = hashlib.sha256()
    for name in _FILES:
        h.update(_read(PROMPTS_DIR / name).encode())
    h.update(_read(PROMPTS_DIR / "topics" / f"{topic}.md").encode())
    h.update(_read(GLOSSARY_PATH).encode())
    return h.hexdigest()


def prompt_version(topic: str) -> str:
    return f"{topic}-{PROMPT_VERSION_SUFFIX}"


class PromptRenderer:
    def system_prompt(self, topic: str) -> str:
        parts = [_read(PROMPTS_DIR / name) for name in _FILES]
        parts.append(_read(PROMPTS_DIR / "topics" / f"{topic}.md"))
        glossary = _read(GLOSSARY_PATH)
        if glossary:
            parts.append("Bảng glossary chuẩn (key | zh | vi):\n" + glossary)
        return "\n\n---\n\n".join(p for p in parts if p)

    def user_prompt(self, bundle: EvidenceBundle) -> str:
        evidence = [
            {
                "id": item.id,
                "kind": item.kind,
                "scope": item.scope,
                "palace_key": item.palace_key,
                "entity_key": item.entity_key,
                "data": item.data,
            }
            for item in bundle.items
        ]
        return (
            f"Chủ đề: {bundle.topic}\n\n"
            "EvidenceBundle (tham chiếu bằng [E###]):\n"
            + json.dumps(evidence, ensure_ascii=False, indent=1)
        )

    def render(
        self, topic: str, bundle: EvidenceBundle
    ) -> tuple[list[dict[str, str]], str, str]:
        messages = [
            {"role": "system", "content": self.system_prompt(topic)},
            {"role": "user", "content": self.user_prompt(bundle)},
        ]
        return messages, prompt_version(topic), template_sha256(topic)

    def repair_messages(
        self, messages: list[dict[str, str]], violations: list[str]
    ) -> list[dict[str, str]]:
        repair = (
            "Bản luận giải trước vi phạm quy tắc căn cứ. Viết lại toàn bộ, "
            "sửa đúng các lỗi sau — chỉ dùng thực thể và [E###] có trong "
            "EvidenceBundle:\n- " + "\n- ".join(violations)
        )
        return [*messages, {"role": "user", "content": repair}]
