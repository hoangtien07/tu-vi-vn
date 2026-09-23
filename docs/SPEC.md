# SPEC V2 — Self-Hosted Ziwei Reasoning System

**Status:** Implementation-freeze candidate (sau council review — xem `COUNCIL_REVIEW.md`)
**Repo:** `tu-vi-vn` · **Ngày:** 2026-09-23

---

## 0. Bối cảnh

Mục tiêu ban đầu: self-host 100% một sản phẩm web Tử Vi hoàn chỉnh lấy cảm hứng từ `Renhuai123/ziwei-doushu` — repo MIT nhưng backend/prompt/kho luận giải (`db-analysis.ts`, `/api/interpret`) là proprietary và đã bị rút khỏi bản open-source. Dataset v3 (518.400 lá số × 13 chủ đề, license cho phép commercial + attribution) tồn tại nhưng **không đủ** để tái tạo backend.

Kết luận sau phân tích ecosystem: **không phục dựng backend proprietary**. Thay vào đó, best-of-breed theo lớp:

```text
Renhuai      = donor UI + true-solar-time reference + dataset (sau này)
x-iztro      = canonical deterministic Ziwei engine (Python binding)
KnowledgePack= structured knowledge (x-iztro schema, zh-CN built-in)
Crazycreate  = donor prompt/provider patterns
ZiweiKnows   = donor UX (match, K-line, share — sau V1)
JS iztro     = differential oracle trong CI (không phải runtime)
LLM          = OpenAI-compatible API của riêng ta
```

---

## 1. Product thesis

Sản phẩm là một **Auditable Ziwei Reasoning System**, không phải "AI report generator".

```text
Birth Input
  → Calendar Conversion
  → Birth-Time Normalization
  → x-iztro (deterministic)
  → Canonical Chart Facts
  → Context Composer (selective domain subgraph)
  → Knowledge + Rules
  → Evidence Bundle
  → Prompt
  → LLM (API của ta) → SSE
  → Vietnamese answer + "Vì sao?" evidence view
```

Điểm khác biệt so với consumer astrology apps: **depth, auditability, self-host, school extensibility, reproducibility** — không phải content volume.

### 1.1 Invariants (không được phá vỡ)

| # | Invariant |
|---|---|
| I1 | **LLM MUST NOT** tính: vị trí sao, 12 cung, tứ hóa, đại hạn/lưu niên/lưu nguyệt/lưu nhật, tam phương tứ chính, cách cục. Tất cả đến từ deterministic engine. |
| I2 | `x-iztro` là **canonical engine duy nhất** trong production. Không dùng đồng thời 2 engine tính lá số runtime. |
| I3 | Không runtime request nào tới Iztro hosted API / Renhuai / bên thứ ba. LLM chỉ gọi `AI_BASE_URL` của ta. |
| I4 | Mọi claim Ziwei quan trọng trong output LLM phải ground vào `EvidenceBundle` (tham chiếu `[E###]`). |
| I5 | `RawBirthInput → CivilBirthMoment → NormalizedBirthMoment` đều được **persist**; chart snapshot là immutable. |
| I6 | Mọi InterpretationRun pin đủ version: engine, profile, normalizer, knowledge, prompt, model. |
| I7 | Product state (user, chart, conversation) thuộc PostgreSQL của ta — không dùng hosted session của vendor. |

---

## 2. Technology freeze

| Layer | Quyết định | Ghi chú |
|---|---|---|
| Web | Next.js + React + TypeScript + Tailwind | UI port chọn lọc từ Renhuai |
| Product API | FastAPI, Python 3.12, Pydantic v2 | modular monolith — **không** microservices |
| ORM | SQLAlchemy 2 + Alembic + asyncpg | |
| Canonical engine | **x-iztro 0.6.1** (pin exact) | Python binding, abi3 wheel, MIT |
| Knowledge | x-iztro KnowledgePack + overlays | built-in pack hiện chỉ zh-CN |
| DB | PostgreSQL 16 | JSONB cho chart/evidence |
| LLM | OpenAI-compatible (`AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`) | httpx, không dùng vendor SDK |
| Streaming | SSE (`metadata/evidence/delta/done`) | không WebSocket |
| Package managers | `uv` (Python), `pnpm` (JS) | |
| **Không dùng (V1)** | RAG, vector DB, embeddings, fine-tune, LangGraph/agents SDK, Redis, Celery, Kafka, microservices, hosted iztro API, `iztro-ziwei-v3`, MCP | |
| CI-only | JS `iztro@2.6.1` differential oracle, Renhuai second oracle | không phải runtime dep |

---

## 3. Engine profile — config là data, không phải code

Không dựa vào default ngầm của library. Mọi chart persist profile đã tạo nó.

```json
{
  "id": "iztro-default-v1",
  "engine": "x-iztro",
  "engineVersion": "0.6.1",
  "fixLeap": true,
  "yearDivide": "normal",
  "horoscopeDivide": "normal",
  "ageDivide": "normal",
  "dayDivide": "forward",
  "algorithm": "default",
  "astroType": "heaven",
  "mutagenTableVersion": "builtin",
  "brightnessTableVersion": "builtin"
}
```

6 switch này **đổi được lá số** (ranh giới Lập Xuân vs Tết, quy ước giờ Tý muộn, trường phái Trung Châu vs default...). School pack sau này (`zhongzhou-v1`, `nihai-v1`, `vietnamese-x-v1`) cùng tồn tại như data — không fork engine.

---

## 4. Canonical birth-data contracts

Ba object riêng biệt — không một DTO mơ hồ:

### 4.1 `RawBirthInput` — đúng nguyên văn user nhập (audit trail, không bao giờ ghi đè)

```json
{
  "calendar": "solar",
  "date": "1990-06-15",
  "time": "14:30",
  "gender": "male",
  "placeName": "Hanoi",
  "timezone": "Asia/Ho_Chi_Minh",
  "latitude": 21.0,
  "longitude": 105.8,
  "leapMonth": false,
  "trueSolarTimeEnabled": true
}
```

### 4.2 `CivilBirthMoment` — sau khi normalize lịch (solar/lunar → Gregorian civil datetime)

```json
{
  "civilDateTime": "1990-06-15T14:30:00",
  "timezone": "Asia/Ho_Chi_Minh",
  "latitude": 21.0,
  "longitude": 105.8,
  "sourceCalendar": "solar",
  "calendarConverterVersion": "..."
}
```

### 4.3 `NormalizedBirthMoment` — sau BirthTimeNormalizer

```json
{
  "civilDateTime": "1990-06-15T14:30:00",
  "normalizedDateTime": "1990-06-15T14:17:42",
  "timezoneOffsetMinutes": 420,
  "dstCorrectionMinutes": 0,
  "longitudeCorrectionMinutes": -8.8,
  "equationOfTimeMinutes": -3.5,
  "totalSolarCorrectionMinutes": -12.3,
  "dateShift": 0,
  "timeIndex": 7,
  "normalizationMode": "true-solar",
  "normalizerVersion": "vn-tst-v1"
}
```

## 5. `BirthTimeNormalizer` — domain module hạng nhất

```text
CivilBirthMoment
  → timezone/history → DST → longitude correction
  → equation of time → date rollover
  → NormalizedBirthMoment
```

- Renhuai `true-solar-time.ts`/`dst-cn.ts` chỉ là **reference** — dữ liệu DST Trung Quốc không được copy nguyên xi làm default Việt Nam.
- Default VN: IANA `Asia/Ho_Chi_Minh` + longitude + equation of time; historical VN timezone rules.
- `to_iztro_time_index(dt)` có boundary tests tường minh: `00:00, 00:59, 01:00, 22:59, 23:00, 23:59`; index 0 = Tý sớm, index 12 = Tý muộn + `dayDivide`.

## 6. `ChartSnapshot` — immutable

```json
{
  "id": "chart_...",
  "birthProfileId": "...",
  "normalizedBirthMomentId": "...",
  "engine": "x-iztro",
  "engineVersion": "0.6.1",
  "engineProfileId": "iztro-default-v1",
  "chartHash": "sha256(normalized + engineVersion + profile)",
  "chartJson": {},
  "patternHits": [],
  "createdAt": "..."
}
```

Engine/config/normalizer thay đổi → tạo `ChartSnapshot` mới, **không mutate** bản cũ.

## 7. Language strategy

`x-iztro` hỗ trợ `vi-VN` nhưng built-in KnowledgePack hiện **chỉ zh-CN**.

```text
AI context     : chart + knowledge theo zh-CN (terminology đáng tin hơn trong training data)
Instructions   : Vietnamese/English
Model output   : tiếng Việt
UI             : language-independent keys (ziweiMaj, careerPalace, sihuaJi...) qua localization layer
```

`domain identity ≠ translated label` — đổi cách gọi tiếng Việt không làm invalidate chart data. Vi overlay pack chỉ làm khi eval cho thấy cần.

## 8. Knowledge architecture

```text
knowledge/
├── base/        iztro-docs (built-in zh-CN pack)
├── schools/     nihai/, custom/      (sau)
└── languages/   vi/                  (sau)
```

- `KnowledgeRegistry` là điểm truy cập duy nhất (`active_pack()`, `version_info()`) — không rải `KnowledgePack.builtin()` khắp code.
- KnowledgePack model sẵn: `stars, star combinations, patterns, palaces, mutagens, concepts` + `base.merged(overlay...)`.
- **KnowledgePack là semantic dictionary, chưa phải complete expert system.** Thiếu quan hệ bậc cao: palace × star × brightness × sihua × đa cung × vận hạn × topic × school priority → dành chỗ `InterpretationRulePack` (optional, chỉ thêm khi eval chứng minh gap).

## 9. `ContextComposer` — mandatory

Không dump nguyên 12 cung + full knowledge cho mọi câu hỏi. Dùng selective domain subgraph:

```text
question/topic → TopicScopePolicy
  → relevant palace → 三方四正 → relevant patterns
  → relevant horoscope scope → knowledge
```

Topic policy ban đầu (mirror 13-topic schema của Renhuai `db-analysis.ts`):

| Topic | Palace chính | V1? |
|---|---|---|
| overview | natal summary + main patterns | ✅ |
| personality | 命宫 | deferred |
| love | 夫妻 | ✅ |
| career | 官禄 | ✅ |
| wealth | 财帛 | ✅ |
| health | 疾厄 (prompt cấm chẩn đoán y khoa) | ✅ |
| family/children/move/friends/home/spirit/parents | 兄弟/子女/迁移/仆役/田宅/福德/父母 | deferred |

Static vs temporal phải tách:

- `"Tôi hợp nghề gì?"` → natal + career context + patterns
- `"Năm 2028 sự nghiệp?"` → natal career + horoscope(2028) + yearly patterns/mutagens
- `"Tháng 6/2028?"` → natal + decadal + yearly + monthly

## 10. `QueryRouter` — 2 mode

- **Mode 1 deterministic (MVP):** UI đã biết intent → route bằng code, không LLM planner. VD: `[Sự nghiệp]` + `[2028]` → `topic=career, scope=yearly, year=2028`.
- **Mode 2 free chat (sau):** tool surface tối đa 4 semantic tools:

```text
get_natal_context
get_topic_context(topic)
get_period_context(year?, month?, day?)
compare_profiles(a, b)
```

Không expose hàng chục hàm x-iztro thô — backend map 4 ops này xuống library calls (theo BFCL lesson: toolset nhỏ → ít lỗi routing).

## 11. `EvidenceBundle` — object quan trọng nhất của V2

```json
{
  "id": "evidence_...",
  "topic": "career",
  "items": [
    {"id": "E001", "kind": "deterministic_fact", "source": "x-iztro", "scope": "careerPalace", "data": {}},
    {"id": "E002", "kind": "pattern", "key": "zi_fu_tong_gong", "source": "x-iztro-pattern-engine"},
    {"id": "E003", "kind": "knowledge", "source": "iztro-docs", "sourceVersion": "...", "key": "zi_fu_tong_gong"},
    {"id": "E004", "kind": "horoscope_fact", "scope": "yearly:2028", "source": "x-iztro"}
  ]
}
```

Kinds V1: `chart_fact, palace_fact, pattern, mutagen, knowledge, horoscope_fact`.

## 12. Evidence-aware generation

Context có evidence IDs; system policy bắt buộc:

```text
- Mọi claim Ziwei quan trọng phải ground ≥1 evidence id
- Không invent stars/palaces/transformations/patterns/horoscope facts
- Dùng [E###] sau claim
- Phân biệt tendency vs concrete event
- Phân biệt natal vs vận hạn
- Trình bày uncertainty khi mơ hồ
```

`GroundingValidator` (deterministic, không phải LLM): extract `[E###]` → verify tồn tại trong bundle → `unknownEvidenceReferences` phải = 0. UI render `[E001]` thành *"Căn cứ ▼"*.

## 13. `InterpretationRun` — immutable, reproducible

```json
{
  "id": "...",
  "chartSnapshotId": "...",
  "topic": "career",
  "targetDate": null,
  "contextComposerVersion": "v1",
  "evidenceBundleId": "...",
  "knowledgePacks": ["iztro-docs@..."],
  "promptVersion": "career-v1",
  "modelProvider": "our-openai-compatible",
  "modelName": "...",
  "temperature": 0.3,
  "contextHash": "...",
  "output": "...",
  "createdAt": "..."
}
```

## 14. `LLMGateway`

```python
class LLMProvider(Protocol):
    async def complete(self, messages, **kw): ...
    async def stream(self, messages, **kw) -> AsyncIterator[str]: ...
```

- Implementation duy nhất V1: `OpenAICompatibleProvider` → `POST {AI_BASE_URL}/chat/completions` qua `httpx`.
- Domain code không biết provider tên gì; sau có `supports_tools / supports_json_schema / supports_reasoning` capability flags.
- Config qua env: `AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_TIMEOUT_SECONDS`. Không bao giờ log API key.

## 15. Prompt architecture

Không giant prompt:

```text
prompts/
├── system.md          — role + invariants + safety policy
├── evidence-policy.md — grounding rules + [E###] contract
├── output-vi.md       — Vietnamese style/terminology
├── topics/            — overview/personality/career/wealth/love/health/...
└── fortune/           — yearly/monthly/daily
```

Baseline: adapt `Crazycreate/Numerology` prompts.ts (MIT), bỏ logic Bát Tự; giữ policies: không invent event, tách tendency/event, cite chart basis, không giấu mâu thuẫn.

**Safety policy (system prompt, không rải rác):** trình bày là luận giải truyền thống/mệnh lý học, không phải chẩn đoán y khoa/tư vấn tài chính/pháp lý; health/investment/legal không được biến thành claim chuyên môn.

## 16. API surface (MVP cố ý nhỏ)

```text
POST /api/charts
GET  /api/charts/{id}
POST /api/charts/{id}/interpret     {topic} | {topic, target:{scope,year}}
POST /api/charts/{id}/chat          (sau vertical slice — optional V1)
GET  /api/charts/{id}/fortune/year/{year}
GET  /health                        (api + db; KHÔNG phụ thuộc AI)
GET  /health/dependencies           (AI dependency state)
```

SSE events: `metadata → evidence → delta* → done`.

## 17. Database model (PostgreSQL, JSONB cho object nặng)

```text
users (v1: single dev user, nhưng giữ user_id để add auth sau)
birth_profiles
raw_birth_inputs
normalized_birth_moments
engine_profiles
chart_snapshots
conversations
messages
evidence_bundles
interpretation_runs
```

Không normalize sao/cung thành hàng chục bảng quan hệ ở V1.

## 18. Repo layout

```text
tu-vi-vn/
├── apps/
│   ├── web/                    Next.js (UI port từ Renhuai)
│   │   ├── app/ components/ features/ lib/
│   └── api/                    FastAPI
│       ├── app/
│       │   ├── main.py
│       │   ├── api/            charts.py, interpretations.py, health.py
│       │   ├── domain/         birth/ chart/ context/ evidence/ interpretation/
│       │   ├── infrastructure/ db/ xiztro/ llm/
│       │   ├── prompts/
│       │   └── settings.py
│       ├── tests/ alembic/ pyproject.toml
├── packages/
│   ├── contracts/              shared DTOs (TS + generated)
│   ├── knowledge/              overlay packs (sau)
│   └── ui/
├── eval/                       cases/ engine/ grounding/ context/ interpretation/
├── scripts/                    differential/ (CI oracle), dev utils
├── infra/                      docker-compose.yml, env/
├── docs/                       SPEC, IMPLEMENTATION_PLAN, EVALUATION, DONORS, COUNCIL_REVIEW
├── pnpm-workspace.yaml
└── AGENTS.md
```

Dependency direction: `api → domain services → ports/interfaces → infrastructure adapters`. Endpoint không chứa business logic. Chỉ `infrastructure/xiztro/` import `x_iztro`.

## 19. Logging & privacy

Log mỗi interpretation: `request_id, chart_id, run_id, engine_version, engine_profile, composer_version, knowledge_version, prompt_version, model_name, latency, token counts`. Không log `AI_API_KEY`, hạn chế PII ngày sinh.

## 20. Rủi ro đã biết & mitigation

| Rủi ro | Mitigation |
|---|---|
| x-iztro pre-1.0, cộng đồng nhỏ | Pin version + JS iztro differential oracle CI + Renhuai second oracle; upgrade qua differential suite mới promote |
| KnowledgePack chưa đủ deep (chỉ zh-CN, semantic dict) | ContextComposer + eval gates; RulePack/vi overlay chỉ khi eval chứng minh gap |
| True solar time VN edge cases | `vn-tst-v1` normalizer + boundary tests bắt buộc trước release |
| LLM hallucinate chart facts | Evidence-only policy + GroundingValidator (unknown [E###] = fail) |
| Model không biết Tử Vi | Eval harness Gate E đo trước khi ship; model choice theo benchmark, không cảm giác |
