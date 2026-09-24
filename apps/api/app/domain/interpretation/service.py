"""InterpretationService — the auditable pipeline (SPEC §12–13).

ChartSnapshot → ContextComposer → EvidenceBuilder → PromptRenderer →
LLMGateway → GroundingValidator → InterpretationRun.

SSE event contract: metadata → evidence → delta* → done | error.
Partial output is never persisted as a completed run.
"""

import datetime as dt
import hashlib
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.birth.contracts import NormalizedBirthMoment
from app.domain.chart.contracts import CanonicalChartDTO, EngineProfile
from app.domain.chart.service import new_id
from app.domain.context.composer import ContextComposer, Topic
from app.domain.evidence.builder import EvidenceBuilder, EvidenceBundle
from app.domain.interpretation.grounding import extract_claims, validate
from app.domain.interpretation.prompts import PromptRenderer
from app.infrastructure.db.models import (
    ChartSnapshot,
    EngineProfileRow,
    InterpretationRun,
    NormalizedBirthMomentRow,
)
from app.infrastructure.db.models import (
    EvidenceBundle as EvidenceBundleRow,
)
from app.infrastructure.llm.openai_compatible import (
    LLMNotConfiguredError,
    LLMProvider,
)
from app.infrastructure.xiztro.knowledge import KnowledgeRegistry

CONTEXT_COMPOSER_VERSION = "v1"
DECODING_REPORT = {"temperature": 0.6}
MAX_REPAIR_ATTEMPTS = 1

Event = dict[str, Any]


class Streamable(Protocol):
    def stream(self, messages: list[dict[str, str]], **kw: Any) -> Any: ...
    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str: ...


def _context_hash(bundle: EvidenceBundle) -> str:
    payload = json.dumps(
        [i.model_dump(mode="json") for i in bundle.items],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _idempotency_key(
    chart_id: str,
    topic: str,
    target: dt.date | None,
    prompt_ver: str,
    model: str,
    template_sha: str,
    context_hash: str,
) -> str:
    raw = "|".join(
        [
            chart_id,
            topic,
            str(target or ""),
            prompt_ver,
            model,
            template_sha,
            context_hash,
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _sse(event: str, data: Any) -> Event:
    return {"event": event, "data": data}


class InterpretationService:
    def __init__(
        self,
        composer: ContextComposer,
        provider: LLMProvider | None,
        renderer: PromptRenderer | None = None,
    ) -> None:
        self._composer = composer
        self._provider = provider
        self._renderer = renderer or PromptRenderer()

    def _load_normalized(
        self, session: Session, snapshot: ChartSnapshot
    ) -> NormalizedBirthMoment:
        row = session.get(
            NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id
        )
        if row is None:
            raise LookupError("normalized birth moment missing")
        return NormalizedBirthMoment.model_validate(row.payload)

    async def run(
        self,
        session: Session,
        snapshot: ChartSnapshot,
        topic: Topic,
        target_date: dt.date | None,
        *,
        conversation_id: str | None = None,
    ) -> AsyncIterator[Event]:
        normalized = self._load_normalized(session, snapshot)
        profile_row = session.get(EngineProfileRow, snapshot.engine_profile_id)
        if profile_row is None:
            raise LookupError("engine profile missing")
        profile = EngineProfile.model_validate(profile_row.content)
        dto = CanonicalChartDTO.model_validate(snapshot.chart_json)

        context = self._composer.compose(
            normalized,
            profile,
            dto,
            topic,
            target_date,
            knowledge=KnowledgeRegistry,
        )
        knowledge_version = KnowledgeRegistry.version_info()["version"]
        bundle = EvidenceBuilder(knowledge_version=knowledge_version).build(
            context, new_id("ev")
        )
        context_hash = _context_hash(bundle)
        session.add(
            EvidenceBundleRow(
                id=bundle.id,
                chart_snapshot_id=snapshot.id,
                context_hash=context_hash,
                payload=bundle.model_dump(mode="json"),
            )
        )

        messages, prompt_ver, template_sha = self._renderer.render(topic, bundle)
        model = getattr(self._provider, "model", "") or ""
        ikey = _idempotency_key(
            snapshot.id,
            topic,
            target_date,
            prompt_ver,
            model,
            template_sha,
            context_hash,
        )

        existing = session.scalar(
            select(InterpretationRun).where(
                InterpretationRun.idempotency_key == ikey
            )
        )
        if existing is not None and existing.status == "completed":
            session.commit()  # persist evidence bundle row
            yield _sse(
                "metadata",
                {
                    "runId": existing.id,
                    "topic": topic,
                    "promptVersion": prompt_ver,
                    "model": model,
                    "replay": True,
                },
            )
            replay_bundle = bundle
            if existing.evidence_bundle_id:
                stored = session.get(
                    EvidenceBundleRow, existing.evidence_bundle_id
                )
                if stored is not None:
                    replay_bundle = EvidenceBundle.model_validate(stored.payload)
            yield _sse("evidence", self._evidence_payload(replay_bundle))
            yield _sse("delta", existing.output_text)
            yield _sse("done", {"runId": existing.id, "replay": True})
            return

        # Failed/abandoned attempts keep their row for the audit trail: free
        # the idempotency key so the retry can claim it on a fresh run row.
        if existing is not None:
            existing.idempotency_key = None

        run = InterpretationRun(
            id=new_id("ir"),
            chart_snapshot_id=snapshot.id,
            evidence_bundle_id=bundle.id,
            conversation_id=conversation_id,
            idempotency_key=ikey,
            topic=topic,
            status="pending",
            version_meta={},
        )
        run.version_meta = {
            "contextComposerVersion": CONTEXT_COMPOSER_VERSION,
            "knowledgePacks": [KnowledgeRegistry.version_info()],
            "promptVersion": prompt_ver,
            "promptTemplateSha256": template_sha,
            "modelProvider": "openai-compatible",
            "modelName": model,
            "decoding": DECODING_REPORT,
            "contextHash": context_hash,
            "targetDate": str(target_date) if target_date else None,
        }
        session.add(run)
        session.commit()

        try:
            yield _sse(
                "metadata",
                {
                    "runId": run.id,
                    "topic": topic,
                    "promptVersion": prompt_ver,
                    "model": model,
                },
            )
            yield _sse("evidence", self._evidence_payload(bundle))

            if self._provider is None:
                run.status = "failed"
                session.commit()
                yield _sse(
                    "error",
                    {"type": "llm_unconfigured", "detail": "AI endpoint not configured"},
                )
                return

            output = ""
            try:
                async for delta in self._provider.stream(messages, **DECODING_REPORT):
                    output += delta
                    yield _sse("delta", delta)
            except LLMNotConfiguredError:
                run.status = "failed"
                session.commit()
                yield _sse(
                    "error",
                    {"type": "llm_unconfigured", "detail": "AI endpoint not configured"},
                )
                return
            except Exception:
                run.status = "failed"
                session.commit()
                yield _sse("error", {"type": "llm_upstream", "detail": "LLM upstream error"})
                return

            result = validate(output, bundle)
            for _ in range(MAX_REPAIR_ATTEMPTS):
                if result.ok:
                    break
                try:
                    output = await self._provider.complete(
                        self._renderer.repair_messages(messages, result.violations),
                        **DECODING_REPORT,
                    )
                except Exception:
                    break
                result = validate(output, bundle)
                if result.ok:
                    # The streamed draft was rejected — replace it wholesale so
                    # displayed output matches the audited output.
                    yield _sse("replace", output)

            if not result.ok:
                run.status = "failed"
                run.output_text = output
                run.version_meta = {
                    **run.version_meta,
                    "groundingViolations": result.violations,
                }
                session.commit()
                yield _sse(
                    "error",
                    {"type": "grounding_failed", "violations": result.violations},
                )
                return

            run.status = "completed"
            run.output_text = output
            run.claims = extract_claims(output)
            run.version_meta = {
                **run.version_meta,
                "orphanClaimFlags": result.orphan_claims,
            }
            session.commit()
            yield _sse("done", {"runId": run.id, "orphanFlags": len(result.orphan_claims)})
        finally:
            # Client disconnect/abort leaves no terminal event — close the
            # run as failed so it doesn't linger as 'pending' (audit keeps
            # the row; a retry frees the idempotency key as usual).
            if run.status == "pending":
                run.status = "failed"
                run.version_meta = {**run.version_meta, "aborted": True}
                session.commit()

    @staticmethod
    def _evidence_payload(bundle: EvidenceBundle) -> dict[str, Any]:
        return {
            "bundleId": bundle.id,
            "items": [
                {
                    "id": i.id,
                    "kind": i.kind,
                    "source": i.source,
                    "scope": i.scope,
                    "palace_key": i.palace_key,
                    "entity_key": i.entity_key,
                    "data": i.data,
                }
                for i in bundle.items
            ],
        }
