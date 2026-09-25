import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import (
    CanonicalChartDTO,
    EngineProfile,
)
from app.domain.chart.service import new_id
from app.domain.context.composer import ContextComposer, TargetScope
from app.domain.evidence.builder import EvidenceBuilder
from app.infrastructure.db.models import (
    ChartSnapshot,
    Conversation,
    EngineProfileRow,
    Message,
    NormalizedBirthMomentRow,
)
from app.infrastructure.llm.openai_compatible import LLMProvider
from app.infrastructure.xiztro.knowledge import KnowledgeRegistry

DECODING_CHAT = {"temperature": 0.7}
MAX_HISTORY = 10
MAX_MESSAGE_LEN = 2000
MAX_FACTS = 60

CHAT_SYSTEM = """Bạn là thầy tử vi hiện đại, trả lời câu hỏi của đương số về lá số dưới đây.
Quy tắc:
- Chỉ dựa vào ngữ cảnh lá số được cung cấp; không tự bịa sao/cung/cách cục.
- Trình bày là luận giải mệnh lý truyền thống, mang tính tham khảo.
- Không đưa tuyên bố xác định về tử vong, tai họa, tuổi thọ; không tư vấn y khoa,
  tài chính, pháp lý như chuyên gia.
- Trả lời tiếng Việt, gọn, đúng ngữ cảnh câu hỏi.

NGỮ CẢNH LÁ SỐ:
{context}
"""


class ChatService:
    def __init__(self, composer: ContextComposer, provider: LLMProvider | None):
        self._composer = composer
        self._provider = provider

    async def respond(
        self,
        session: Session,
        snapshot: ChartSnapshot,
        user_text: str,
        conversation_id: str | None,
        target_date: dt.date | None = None,
        target_scope: TargetScope | None = None,
    ) -> dict[str, Any]:
        if self._provider is None:
            raise RuntimeError("llm_unconfigured")

        normalized = _load_normalized(session, snapshot)
        profile = _load_profile(session, snapshot)
        context = self._composer.compose(
            normalized,
            profile,
            CanonicalChartDTO.model_validate(snapshot.chart_json),
            "overview",
            target_date,
            target_scope=target_scope,
            knowledge=KnowledgeRegistry,
        )
        bundle = EvidenceBuilder().build(context, new_id("ev"))
        facts = "\n".join(
            f"- {item.kind}"
            f"{':' + item.palace_key if item.palace_key else ''}"
            f"{':' + item.entity_key if item.entity_key else ''}"
            f" → {item.data}"
            for item in bundle.items[:MAX_FACTS]
        )

        if conversation_id:
            convo = session.get(Conversation, conversation_id)
            if convo is None or convo.chart_snapshot_id != snapshot.id:
                raise LookupError("conversation not found")
        else:
            convo = Conversation(
                id=new_id("cv"), chart_snapshot_id=snapshot.id
            )
            session.add(convo)
            session.flush()

        history = list(
            session.scalars(
                select(Message)
                .where(Message.conversation_id == convo.id)
                .order_by(Message.created_at)
            )
        )[-MAX_HISTORY:]

        messages: list[dict[str, str]] = [
            {"role": "system", "content": CHAT_SYSTEM.format(context=facts)},
            *[{"role": m.role, "content": m.content} for m in history],
            {"role": "user", "content": user_text},
        ]
        reply = await self._provider.complete(messages, **DECODING_CHAT)

        session.add(
            Message(
                id=new_id("msg"),
                conversation_id=convo.id,
                role="user",
                content=user_text,
            )
        )
        session.add(
            Message(
                id=new_id("msg"),
                conversation_id=convo.id,
                role="assistant",
                content=reply,
            )
        )
        session.commit()
        return {"conversationId": convo.id, "reply": reply}


def _load_normalized(
    session: Session, snapshot: ChartSnapshot
) -> NormalizedBirthMoment:
    row = session.get(
        NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id
    )
    if row is None:
        raise LookupError("normalized birth moment missing")
    return NormalizedBirthMoment.model_validate(row.payload)


def _load_profile(session: Session, snapshot: ChartSnapshot) -> EngineProfile:
    row = session.get(EngineProfileRow, snapshot.engine_profile_id)
    if row is None:
        raise LookupError("engine profile missing")
    return EngineProfile.model_validate(row.content)
