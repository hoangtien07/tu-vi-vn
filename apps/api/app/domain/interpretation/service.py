"""InterpretationService — the auditable pipeline (SPEC §12–13).

ChartSnapshot → ContextComposer → EvidenceBuilder → PromptRenderer →
LLMGateway → GroundingValidator → InterpretationRun.

Hợp bàn (`run_pair`, SPEC_COMPATIBILITY): two snapshots compose one
side-tagged bundle; chart_a keeps `chart_snapshot_id`, chart_b lands on
`partner_chart_snapshot_id` — request order is part of the idempotency key.

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
from app.domain.context.comparison import COMPATIBILITY_TOPIC, ComparisonComposer
from app.domain.context.composer import ContextComposer, TargetScope, Topic
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
    target_scope: str | None,
    target: dt.date | None,
    namespace: str | None,
    prompt_ver: str,
    model: str,
    template_sha: str,
    context_hash: str,
) -> str:
    raw = "|".join(
        [
            namespace or "",
            chart_id,
            topic,
            target_scope or "",
            str(target or ""),
            prompt_ver,
            model,
            template_sha,
            context_hash,
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


# A `pending` row older than this is a zombie (hard crash skipped the
# abort-finally) — treated as failed so its idempotency key can be freed.
_PENDING_TTL = dt.timedelta(minutes=10)


def _live_pending(run: InterpretationRun) -> bool:
    created = run.created_at
    if created is None:
        return False
    if created.tzinfo is not None:
        created = created.astimezone(dt.UTC).replace(tzinfo=None)
    return dt.datetime.now(dt.UTC).replace(tzinfo=None) - created < _PENDING_TTL


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

    def _load_normalized(self, session: Session, snapshot: ChartSnapshot) -> NormalizedBirthMoment:
        row = session.get(NormalizedBirthMomentRow, snapshot.normalized_birth_moment_id)
        if row is None:
            raise LookupError("normalized birth moment missing")
        return NormalizedBirthMoment.model_validate(row.payload)

    def _load_profile(self, session: Session, snapshot: ChartSnapshot) -> EngineProfile:
        profile_row = session.get(EngineProfileRow, snapshot.engine_profile_id)
        if profile_row is None:
            raise LookupError("engine profile missing")
        return EngineProfile.model_validate(profile_row.content)

    def load_chart(
        self, session: Session, snapshot: ChartSnapshot
    ) -> tuple[NormalizedBirthMoment, EngineProfile, CanonicalChartDTO]:
        return (
            self._load_normalized(session, snapshot),
            self._load_profile(session, snapshot),
            CanonicalChartDTO.model_validate(snapshot.chart_json),
        )

    async def run(
        self,
        session: Session,
        snapshot: ChartSnapshot,
        topic: Topic,
        target_date: dt.date | None,
        *,
        target_scope: TargetScope | None = None,
        namespace: str | None = None,
        conversation_id: str | None = None,
    ) -> AsyncIterator[Event]:
        normalized, profile, dto = self.load_chart(session, snapshot)

        context = self._composer.compose(
            normalized,
            profile,
            dto,
            topic,
            target_date,
            target_scope,
            knowledge=KnowledgeRegistry,
        )
        knowledge_version = KnowledgeRegistry.version_info()["version"]
        bundle = EvidenceBuilder(knowledge_version=knowledge_version).build(context, new_id("ev"))
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
            target_scope,
            target_date,
            namespace,
            prompt_ver,
            model,
            template_sha,
            context_hash,
        )

        existing = session.scalar(
            select(InterpretationRun).where(InterpretationRun.idempotency_key == ikey)
        )
        if existing is not None and existing.status == "completed":
            session.commit()  # persist evidence bundle row
            async for ev in self._replay(session, existing, bundle, topic, prompt_ver, model):
                yield ev
            return

        # A run still streaming must keep its key — a duplicate request gets an
        # explicit in-progress signal instead of spawning a second LLM stream.
        if existing is not None and existing.status == "pending" and _live_pending(existing):
            session.rollback()  # drop the duplicate evidence bundle row
            yield _sse(
                "error",
                {"type": "run_in_progress", "runId": existing.id},
            )
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
            "targetScope": target_scope,
            "namespace": namespace,
        }
        session.add(run)
        session.commit()

        async for ev in self._execute(session, run, bundle, messages, prompt_ver, model):
            yield ev

    async def run_pair(
        self,
        session: Session,
        snapshot_a: ChartSnapshot,
        snapshot_b: ChartSnapshot,
        target_date: dt.date | None,
        *,
        target_scope: TargetScope | None = None,
        namespace: str | None = None,
    ) -> AsyncIterator[Event]:
        """Hợp bàn run — one audit row, chart_a on chart_snapshot_id, chart_b
        on partner_chart_snapshot_id. Request order is part of the ikey so
        (A,B) and (B,A) never replay each other's labels."""
        normalized_a, profile_a, dto_a = self.load_chart(session, snapshot_a)
        normalized_b, profile_b, dto_b = self.load_chart(session, snapshot_b)

        context = ComparisonComposer(self._composer.engine).compose_pair(
            normalized_a,
            profile_a,
            dto_a,
            normalized_b,
            profile_b,
            dto_b,
            target_date,
            target_scope,
            knowledge=KnowledgeRegistry,
        )
        knowledge_version = KnowledgeRegistry.version_info()["version"]
        bundle = EvidenceBuilder(knowledge_version=knowledge_version).build(context, new_id("ev"))
        context_hash = _context_hash(bundle)
        session.add(
            EvidenceBundleRow(
                id=bundle.id,
                chart_snapshot_id=snapshot_a.id,
                context_hash=context_hash,
                payload=bundle.model_dump(mode="json"),
            )
        )

        messages, prompt_ver, template_sha = self._renderer.render(COMPATIBILITY_TOPIC, bundle)
        model = getattr(self._provider, "model", "") or ""
        ikey = _idempotency_key(
            f"{snapshot_a.id}|{snapshot_b.id}",
            COMPATIBILITY_TOPIC,
            target_scope,
            target_date,
            namespace,
            prompt_ver,
            model,
            template_sha,
            context_hash,
        )

        existing = session.scalar(
            select(InterpretationRun).where(InterpretationRun.idempotency_key == ikey)
        )
        if existing is not None and existing.status == "completed":
            session.commit()
            async for ev in self._replay(
                session, existing, bundle, COMPATIBILITY_TOPIC, prompt_ver, model
            ):
                yield ev
            return

        if existing is not None and existing.status == "pending" and _live_pending(existing):
            session.rollback()
            yield _sse(
                "error",
                {"type": "run_in_progress", "runId": existing.id},
            )
            return

        if existing is not None:
            existing.idempotency_key = None

        run = InterpretationRun(
            id=new_id("ir"),
            chart_snapshot_id=snapshot_a.id,
            partner_chart_snapshot_id=snapshot_b.id,
            evidence_bundle_id=bundle.id,
            idempotency_key=ikey,
            topic=COMPATIBILITY_TOPIC,
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
            "targetScope": target_scope,
            "namespace": namespace,
            "chartB": snapshot_b.id,
            "sides": {"a": snapshot_a.id, "b": snapshot_b.id},
        }
        session.add(run)
        session.commit()

        async for ev in self._execute(session, run, bundle, messages, prompt_ver, model):
            yield ev

    async def _replay(
        self,
        session: Session,
        existing: InterpretationRun,
        bundle: EvidenceBundle,
        topic: str,
        prompt_ver: str,
        model: str,
    ) -> AsyncIterator[Event]:
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
            stored = session.get(EvidenceBundleRow, existing.evidence_bundle_id)
            if stored is not None:
                replay_bundle = EvidenceBundle.model_validate(stored.payload)
        yield _sse("evidence", self._evidence_payload(replay_bundle))
        yield _sse("delta", existing.output_text)
        yield _sse("done", {"runId": existing.id, "replay": True})

    async def _execute(
        self,
        session: Session,
        run: InterpretationRun,
        bundle: EvidenceBundle,
        messages: list[dict[str, str]],
        prompt_ver: str,
        model: str,
    ) -> AsyncIterator[Event]:
        try:
            yield _sse(
                "metadata",
                {
                    "runId": run.id,
                    "topic": run.topic,
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
                        self._renderer.repair_messages(messages, result.violations, bundle),
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
