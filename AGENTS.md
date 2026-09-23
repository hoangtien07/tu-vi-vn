# AGENTS.md — tu-vi-vn

Hướng dẫn cho coding agents (Devin/Codex/...) làm việc trong repo này. Đọc `docs/SPEC.md` và `docs/IMPLEMENTATION_PLAN.md` trước khi code.

## Invariants — vi phạm = reject PR

1. **LLM không tính lá số.** Sao, cung, tứ hóa, vận hạn, cách cục đều từ `x-iztro`. LLM chỉ diễn giải từ `EvidenceBundle`.
2. **`x-iztro` là canonical engine duy nhất** trong production. Chỉ `apps/api/app/infrastructure/xiztro/` được `import x_iztro`.
3. **Không runtime request ra ngoài** ngoài `AI_BASE_URL` của project. Không hosted Iztro API, không `iztro-ziwei-v3`.
4. **Mọi claim LLM quan trọng phải cite `[E###]`** từ EvidenceBundle; `GroundingValidator` reject unknown refs.
5. **Persist 3 birth objects** (raw/civil/normalized); `ChartSnapshot` và `InterpretationRun` immutable, pin đủ versions.
6. **Secrets chỉ qua env** (`AI_API_KEY`...). Không commit `.env`, không log key, hạn chế log PII ngày sinh.

## Cấm ở V1

LangGraph/agent frameworks · Redis · Celery · Kafka · vector DB · embeddings · RAG · fine-tune · microservices · WebSocket · vendor AI SDK · fork nguyên Renhuai làm architecture · duplicate x-iztro domain logic · xử lý Dataset v3 vào runtime.

## Cấu trúc & conventions

- Monorepo: `apps/web` (Next.js+TS+Tailwind, pnpm), `apps/api` (FastAPI+Python 3.12, uv, Pydantic v2, SQLAlchemy 2, Alembic), `packages/`, `eval/`, `infra/`, `scripts/`, `docs/`.
- Dependency direction: `api → domain → ports → infrastructure`. Endpoint không chứa business logic.
- FE chỉ nhận `CanonicalChartDTO` — không leak x-iztro/Python types lên UI.
- Donor code (Renhuai/ZiweiKnows/Crazycreate — MIT) giữ attribution header + ghi nguồn trong commit message. `dst-cn.ts` data TQ không được làm default VN.
- Migrations qua Alembic — không sửa schema thủ công.

## Commands

```bash
# api (trong apps/api)
uv sync && uv run pytest          # tests
uv run ruff check && uv run mypy  # lint+types
uv run uvicorn app.main:app --reload

# web (trong apps/web)
pnpm install && pnpm lint && pnpm typecheck && pnpm dev

# full stack
docker compose -f infra/docker-compose.yml up
```

## PR rules

- Minimal focused edits; không đụng file ngoài scope.
- Chạy lint+typecheck+tests của phần sửa trước khi mở PR.
- Thay engine version / normalizer / prompt → bump version field tương ứng, không mutate snapshot/run cũ.
- Test bắt buộc: normalization boundary (SPEC §5), engine regression fixture, grounding `unknownEvidenceReferences = 0`.
