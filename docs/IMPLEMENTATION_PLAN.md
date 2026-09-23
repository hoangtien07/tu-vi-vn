# IMPLEMENTATION PLAN V1 — tu-vi-vn

**Status:** READY TO IMPLEMENT
**Mục tiêu:** Vertical slice end-to-end chứng minh toàn bộ kiến trúc, KHÔNG maximize features.

Slice phải chạy được:

```text
Nhập ngày giờ sinh
→ chuẩn hóa thời gian (vn-tst-v1)
→ x-iztro lập lá số
→ render 12 cung
→ chọn topic (Tổng quan / Sự nghiệp / Tài vận / Tình cảm / Sức khỏe)
→ ContextComposer → EvidenceBundle
→ AI API của ta (SSE)
→ stream luận giải tiếng Việt
→ "Vì sao?" evidence drawer
→ lưu toàn bộ vào PostgreSQL
+ 1 case động: Sự nghiệp năm {year}
```

**Nguyên tắc:** clean repo, không fork nguyên Renhuai. *Reuse source code, not architecture debt.* Deterministic backend slice trước, AI sau — nếu checkpoint deterministic sai thì phần AI chỉ "sai đẹp hơn".

---

## Phase 0 — Bootstrap (commit 1)

- [ ] Monorepo skeleton theo `SPEC.md` §18: `apps/web` (Next.js 15, TS, Tailwind, pnpm), `apps/api` (FastAPI, Python 3.12, uv, pyproject), `packages/`, `eval/`, `infra/`, `scripts/`, `docs/`
- [ ] `infra/docker-compose.yml`: `web`, `api`, `postgres` (16). Không Redis.
- [ ] `infra/env/.env.example`: `DATABASE_URL`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `AI_TIMEOUT_SECONDS`
- [ ] `GET /health` (api+db), `GET /health/dependencies` (AI — không block app health)
- [ ] ruff + mypy strict-lite cho api; eslint + tsc cho web; CI chạy lint+typecheck+pytest

## Phase 1 — Contracts & persistence (commit 2, 4)

- [ ] `domain/birth/contracts.py`: `RawBirthInput`, `CivilBirthMoment`, `NormalizedBirthMoment` (Pydantic theo SPEC §4)
- [ ] `EngineProfile` + seed `iztro-default-v1` (SPEC §3)
- [ ] Alembic init; bảng: `birth_profiles, raw_birth_inputs, normalized_birth_moments, engine_profiles, chart_snapshots, conversations, messages, evidence_bundles, interpretation_runs` (JSONB cho chart/evidence)
- [ ] `chart_hash = sha256(normalized + engine_version + profile)`; chart snapshot immutable

## Phase 2 — Birth normalization (commit 5)

- [ ] `domain/birth/calendar.py`: solar/lunar → `CivilBirthMoment` (dùng `lunar_python`/`lunardate` — chọn lib có VN lunar đúng)
- [ ] `domain/birth/normalizer.py` `BirthTimeNormalizer` Protocol + impl `vn-tst-v1`: timezone (IANA) → DST/historical VN → longitude correction → equation of time → date rollover → `NormalizedBirthMoment.timeIndex`
- [ ] Reference đọc: `Renhuai lib/ziwei/true-solar-time.ts` (MIT). **Không** copy `dst-cn.ts` làm default VN.
- [ ] Boundary tests bắt buộc: `00:00/00:59/01:00/22:59/23:00/23:59`, index 0 vs 12 (晚子时 + `dayDivide`), correction qua ngày trước/sau, thiếu tọa độ, lunar→solar, tháng nhuận
- [ ] `POST /api/charts` trả `{chartId, birth:{raw, normalized}, chart}`

## Phase 3 — Engine adapter (commit 3)

- [ ] `infrastructure/xiztro/engine.py` — `XiztroEngine` implement `ZiweiEngine` Protocol:

```python
class ZiweiEngine(Protocol):
    def cast_chart(self, birth: NormalizedBirthMoment, profile: EngineProfile) -> CanonicalChart: ...
    def get_horoscope(self, chart: CanonicalChart, target: date) -> HoroscopeContext: ...
    def get_surrounded_context(self, chart: CanonicalChart, palace_key: str) -> DomainContext: ...
```

- [ ] Chỉ file này `import x_iztro`. `astro.by_solar(normalized_date, time_index, gender, language="zh-CN", config=...)`
- [ ] `CanonicalChartDTO` (SPEC + PLAN §11): meta/palaces/patterns/engine — FE chỉ ăn DTO của ta, không leak Python object
- [ ] `GET /api/charts/{id}`
- [ ] Fixture regression test: input + profile → expected facts (命宫/身宫/chính tinh/tứ hóa/patterns), không chỉ snapshot full JSON
- [ ] `scripts/differential/` (CI): x-iztro vs JS iztro@2.6.1 trên N random + boundary cases; classify mismatch (bug/school/config/normalization)

## Phase 4 — Chart UI (commit 6)

- [ ] Port chọn lọc từ Renhuai (MIT): `ChartBoard`, `PalaceCell`, `BirthForm`, `TimeNav` cơ bản → `apps/web/features/chart/`
- [ ] Adapter `CanonicalChartDTO → RenhuaiChartViewModel` trong `features/chart/adapters/` — assumption của Renhuai không nhiễm vào API contract
- [ ] Trang `/` (birth form), `/chart/{id}` (12 cung)

## Phase 5 — Knowledge + Context + Evidence (commit 7, 8)

- [ ] `infrastructure/xiztro/knowledge.py` — `KnowledgeRegistry`: `KnowledgePack.builtin("zh-CN")` load 1 lần, `version_info()`
- [ ] `domain/context/composer.py` — `ContextComposer.compose(chart, topic, target) -> ComposedContext`; `TOPIC_POLICY` (SPEC §9); overview = broad natal, topic khác = palace + tam phương tứ chính + patterns + mutagens liên quan
- [ ] `domain/evidence/builder.py` — `EvidenceBuilder`: `ComposedContext → EvidenceBundle` với stable IDs `E001...`
- [ ] Tests: career phải chứa career palace + 三方四正 + relevant patterns; career+2028 phải chứa thêm horoscope 2028; không dump toàn bộ chart

## Phase 6 — LLM pipeline (commit 9, 10)

- [ ] `infrastructure/llm/openai_compatible.py` — `LLMProvider` Protocol + httpx impl, env config (SPEC §14)
- [ ] `app/prompts/` theo SPEC §15 (adapt Crazycreate, bỏ Bát Tự, giữ evidence/anti-invent policies + safety VN)
- [ ] `PromptRenderer`: topic + ComposedContext + EvidenceBundle → `messages[]`
- [ ] `POST /api/charts/{id}/interpret` → pipeline: ChartSnapshot → ContextComposer → EvidenceBuilder → PromptRenderer → LLMGateway → GroundingValidator → InterpretationRun → SSE (`metadata, evidence, delta, done`)
- [ ] `GroundingValidator`: extract `[E###]` → verify tồn tại; `unknownEvidenceReferences = 0`
- [ ] InterpretationRun persist đủ version metadata (SPEC §13)
- [ ] UI: interpretation panel 5 tabs + "Vì sao?" evidence drawer (render `Căn cứ ▼`, không raw `[E###]`)

## Phase 7 — Yearly fortune + chat (commit 11)

- [ ] `GET /api/charts/{id}/fortune/year/{year}` — `chart.horoscope(...)`, adapter owns date convention
- [ ] `interpret` với `{topic, target:{scope:"yearly", year}}`
- [ ] `/api/charts/{id}/chat` (simple): system + domain context hiện tại + last N turns; chat không được thay thế chart context
- [ ] `Conversation`/`Message` persist

## Phase 8 — Eval gates (commit 12)

- [ ] `eval/` cases: `birth-normalization.json`, `chart-regression.json`, `topic-routing.json`, `grounding.json`, `interpretation.json` (~50 cases trước, không hàng nghìn)
- [ ] Gates A–E theo `EVALUATION.md`; fail gate → block release

## Sau V1 (Phase 2+ — KHÔNG làm trước khi V1 done + benchmark)

```text
Auth, multi-profile, compatibility (hợp bàn), K-line, share cards, PDF,
流月/流日/流时, Vietnamese KnowledgePack overlay, InterpretationRulePack,
Dataset v3 mining (eval/knowledge/fine-tune), RAG (chỉ nếu eval chứng minh cần),
tool-calling chat mode (4 semantic tools), model routing theo task
```

Gate trước Phase 2: chạy 20–30 charts × 5 topics qua vài candidate models; so sánh grounding/specificity/consistency/VN quality/latency/cost → quyết định đầu tư tiếp vào model / prompts / RulePack / vi pack / dataset mining.

---

## Commit sequence (đề xuất)

| # | Commit |
|---|---|
| 1 | `chore: bootstrap monorepo` |
| 2 | `feat: add birth domain contracts` |
| 3 | `feat: integrate x-iztro engine adapter` |
| 4 | `feat: persist immutable chart snapshots` |
| 5 | `feat: add birth-time normalization` |
| 6 | `feat: render canonical chart UI` |
| 7 | `feat: add knowledge registry and context composer` |
| 8 | `feat: add evidence bundles` |
| 9 | `feat: integrate configurable OpenAI-compatible LLM` |
| 10 | `feat: stream grounded interpretation` |
| 11 | `feat: add yearly fortune interpretation` |
| 12 | `test: add architecture release gates` |

## Definition of Done — Vertical Slice V1

- [ ] Birth profile nhập được; raw/civil/normalized đều persisted
- [ ] x-iztro cast chart deterministic; engine version + profile persisted; snapshot immutable
- [ ] UI 12 cung render từ `CanonicalChartDTO`
- [ ] 5 topics (overview/career/wealth/love/health) chạy được; career+year chạy được
- [ ] KnowledgePack vào context không qua RAG; ContextComposer selective
- [ ] EvidenceBundle tồn tại trước khi gọi LLM; `[E###]` validated
- [ ] LLM chỉ qua `AI_BASE_URL` configurable; SSE streaming; "Vì sao?" xem được evidence
- [ ] Conversation + InterpretationRun lưu local
- [ ] Không runtime request nào tới Iztro/Renhuai
- [ ] `docker compose up` chạy được toàn bộ trừ AI endpoint (config)
- [ ] Critical deterministic tests pass

## DO NOT (đưa vào mọi implementation prompt)

```text
LangGraph / agent frameworks, Redis, Celery, Kafka, vector DB, embeddings,
RAG, process Dataset v3, fine-tune, microservices, hosted Iztro API,
iztro-ziwei-v3 runtime, LLM tính lá số, fork nguyên Renhuai làm architecture,
duplicate x-iztro domain logic, WebSocket, vendor AI SDK
```
