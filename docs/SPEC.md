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
| I8 | Mọi layer (Evidence, Router, Composer, persistence) địa chỉ entity bằng **stable keys** (`soulPalace`, `lianzhenMaj`, `sha_po_lang`, `sihuaLu`) — tuyệt đối không bằng tên đã dịch (name lookup language-dependent, ambiguous). |

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

**Hard rule (verified footgun x-iztro 0.6.1):** `ChartConfig` LUÔN rebuild từ row `engine_profiles` — không bao giờ rehydrate từ `chart.to_dict()['config']` vì x-iztro **drop** custom `mutagens`/`brightness` khi serialize → silent revert về default.

---

## 4. Canonical birth-data contracts

Ba object riêng biệt — không một DTO mơ hồ:

### 4.1 `RawBirthInput` — đúng nguyên văn user nhập (audit trail, không bao giờ ghi đè)

```json
{
  "calendar": "solar",
  "date": "1990-06-15",
  "time": "14:30",
  "timeUnknown": false,
  "gender": "male",
  "placeName": "Hanoi",
  "birthRegion": "north",
  "timezone": "Asia/Ho_Chi_Minh",
  "latitude": 21.0,
  "longitude": 105.8,
  "leapMonth": false,
  "trueSolarTimeEnabled": true
}
```

- `calendar: solar|lunar` + `leapMonth` — VN users nhập **âm lịch** rất phổ biến; lunar→solar resolve bằng `by_lunar` native của x-iztro (verified hỗ trợ `is_leap_month`).
- `birthRegion` (north|central|south) — bắt buộc cho birth trước ~1975 (xem §5 về +08 window).
- `timeUnknown` — flag optional thêm sớm để tránh schema migration sau. Luồng V1: cast provisional chart với default `timeIndex` + caveat `giờ chưa rõ` trong mọi evidence/output (caveats mechanism — donor Numerology); hour-inference flow (hỏi high-discrimination questions → converge giờ khả dĩ) deferred, donor `hourinfer.ts` của Numerology sẵn.

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
  "correctedSolarDate": "1990-06-15",
  "timeIndex": 7,
  "tzKey": "Asia/Ho_Chi_Minh",
  "tzdataVersion": "2025b",
  "resolvedOffsetMinutes": 420,
  "normalizationMode": "true-solar",
  "normalizerVersion": "vn-tst-v1"
}
```

Engine input là cặp `(correctedSolarDate, timeIndex)` — `timeIndex` có **13 slot 0–12** (0 = Tý sớm 00–01h, 12 = Tý muộn 23–24h). TST correction có thể kéo birth qua ranh giới 2h **và** qua boundary 23:00 → đổi cả civil date lẫn day-attribution (tương tác `dayDivide`).

## 5. `BirthTimeNormalizer` — domain module hạng nhất

```text
CivilBirthMoment
  → VN tz rule table (region-aware) → longitude correction
  → equation of time → date rollover
  → NormalizedBirthMoment (correctedSolarDate, timeIndex 0–12)
```

- Renhuai `true-solar-time.ts`/`dst-cn.ts` chỉ là **reference** — dữ liệu DST Trung Quốc không được copy nguyên xi làm default Việt Nam.
- **Không build generic DST machinery** — tzdb có 0 DST periods cho VN. Công việc VN thật là **bảng quy tắc VN theo vùng** (versioned data trong `vn-tst-v1`, ~10 dòng, cite tzdb + backzone/Trần) — **không** resolve bằng IANA zone name: `Asia/Hanoi` KHÔNG tồn tại trong tzdata rearguard (Ubuntu/Debian drop zone khác nhau chỉ pre-1970; PyPI `tzdata` wheel cũng thiếu → `ZoneInfoNotFoundError` trên Docker Debian).
- Quy tắc VN đúng (tzdb backzone): Hà Nội **+08 tới 1954-10** (ngày giờ không rõ trong tzdb → flag ambiguous), sau đó **+07 liên tục**; Sài Gòn +08 từ 1960-01-01 → 1975-06-12 23:00 (sau +07), quirk +07 1955-07-01→1959-12-31 với blip +07 đúng 1h ở ranh 1959→1960. **Divergence windows** Hà Nội(+07) vs Sài Gòn(+08): (a) 1954-10 → 1955-07-01, (b) 1960-01-01 → 1975-06-12 23:00 — tổng ~20,7 năm ảnh hưởng lá số người sinh miền Bắc.
- Birth trong divergence window mà thiếu `birthRegion` → **warn/chặn**, tuyệt đối không default im lặng theo Sài Gòn.
- `NormalizedBirthMoment` ghi `tzKey + tzdataVersion + resolvedOffsetMinutes` cho provenance.
- Default hiện đại: `Asia/Ho_Chi_Minh` (+07) + longitude + equation of time (optional).
- **Quyền sở hữu Tý muộn (23:00–24:00):** normalizer trả `(correctedSolarDate, timeIndex)` nguyên trạng — day roll do `EngineProfile.dayDivide` sở hữu độc quyền bên trong engine. Normalizer tự roll ngày sẽ gây double-roll.
- `to_iztro_time_index(dt)` có boundary tests tường minh: `00:00, 00:59, 01:00, 22:59, 23:00, 23:59`; index 0 = Tý sớm, index 12 = Tý muộn + `dayDivide`.
- Eval cases bắt buộc thêm: birth ±30 phút quanh mọi hour boundary, boundary 23:00, ranh giới Tết, longitude cực trị VN (Móng Cái ~107.9°E vs Cà Mau ~104.8°E → TST lệch tới ~13 phút so với kinh tuyến 105°E), và các ngày ranh tz VN: `1947-04-01, 1954-10, 1955-07-01, 1959-12-31/1960-01-01, 1975-06-12/13`.

## 6. `ChartSnapshot` — immutable

```json
{
  "id": "chart_...",
  "birthProfileId": "...",
  "normalizedBirthMomentId": "...",
  "engine": "x-iztro",
  "engineVersion": "0.6.1",
  "engineProfileId": "iztro-default-v1",
  "chartHash": "sha256(canonical_json(NormalizedBirthMoment) + engineVersion + profileContent + normalizerVersion + dtoSchemaVersion)",
  "dtoSchemaVersion": 1,
  "chartJson": {},
  "patternHits": [],
  "createdAt": "..."
}
```

Engine/config/normalizer thay đổi → tạo `ChartSnapshot` mới, **không mutate** bản cũ.

`chartJson` là **CanonicalChartDTO của ta** (palaces/stars/mutagens keyed bằng `*_key` language-independent của x-iztro), không phải JSON thô của engine — một mapper duy nhất trong `infrastructure/xiztro`, DTO sống ở `packages/contracts`, có `schemaVersion`. JS-iztro oracle cũng map về cùng DTO cho Gate B. CI import-lint cấm `import x_iztro` ngoài `infrastructure/`.

**Reproducibility contract:** mục tiêu là *reproduce decision inputs deterministically* (không hứa byte-for-byte output với remote model). Canonical JSON = sorted keys + UTF-8 + no whitespace; hash trên CanonicalChartDTO, không hash engine text. Evidence items có ordering rule deterministic (stable sort theo `type, palace_key, entity_key`) nếu không `contextHash` không ổn định.

## 7. Language strategy

`x-iztro` i18n `vi-VN` **hoàn chỉnh** cho chart labels (Mệnh, Liêm Trinh, Thổ Ngũ Cục...) — verified language **không** ảnh hưởng computation. Nhưng built-in KnowledgePack **chỉ zh-CN** (`vi-VN` raise IztroError).

```text
Chart (engine)     : language='vi-VN' → evidence chart-facts trùng ngôn ngữ UI
Knowledge for LLM  : explicit KnowledgePack.builtin('zh-CN') → prose zh cho LLM đọc-và-dịch
Instructions       : Vietnamese/English
Model output       : tiếng Việt
UI                 : language-independent keys (ziweiMaj, careerPalace, sihuaJi...) qua localization layer
```

`domain identity ≠ translated label` — đổi cách gọi tiếng Việt không làm invalidate chart data; `chartHash` không chứa language (display-only). Vi overlay pack chỉ làm khi eval cho thấy cần.

**Glossary zh→vi là V1 artifact bắt buộc** (không nhầm với vi KnowledgePack deferred): sinh ~200–400 dòng từ chính i18n table vi-VN của x-iztro (14 chính tinh, ~90 phụ/sát tinh, 12 cung, tứ hóa, đại hạn/lưu niên/tiểu hạn, brightness, 64 pattern keys — chuẩn Hán-Việt: Mệnh, Tử Nữ, Phu Thê, Nô Bộc, Kình Dương, Địa Kiếp, Triệt Không, Tuần Không, Lai Nhân) → `packages/knowledge/glossary-vi.md`, inject vào prompt + GroundingValidator flag surface-form lệch glossary. Thiếu nó Gate E fail ngay trên terminology consistency.

Footnotes verified trên 0.6.1: `lunar_date` trong chart facts luôn là chữ Hán số ở mọi language (`'二〇〇〇年七月十七'`, by design) → UI/evidence cần formatter vi định danh (`'17/7 âm lịch 2000'` / stem-branch) — không để chuỗi Hán lọt vào EvidenceBundle/UI. Method `astrolabe_to_prompt` chỉ tồn tại trong README — Python binding 0.6.1 **không có**; dùng `to_text()`/`to_json()`.

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

**Knowledge excerpt policy:** built-in pack zh là essay nhiều đoạn (~400–800+ chars/sao). Không dump nguyên — excerpt theo aspect (~150–300 chars/sao/aspect) từ `StarEntry.attributes`/category; evidence kind `knowledge` được đánh dấu là *lore chung* (không phải chart fact) để validator phân biệt được.

**Overview = compact full-chart render** (`to_text` ~7.5k chars ≈ 2–2.5k tokens — rẻ) **+ summary đại vận hiện tại & kế tiếp** (đại hạn palace + stem/branch + range tuổi mụ — gần như free vì composer đã handle horoscope scope; mọi competitor VN đều surface Đại vận), topics khác = selective subgraph. Đừng over-engineer selectivity cho overview.

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

`horoscope(target_date)` nhận **solar date đầy đủ** và trả đủ 6 scopes trong 1 call → composer phải **chỉ chọn scopes cần** (vd: yearly+decadal+age cho topic năm), không dump cả object.

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

Evidence IDs **stable per InterpretationRun** — allocator global trong phạm vi run/conversation (hoặc namespaced `c1.E003` khi nhiều context-build calls), tránh collision `E001` giữa các calls ở Mode 2.

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

`GroundingValidator` (deterministic, không phải LLM) — 4 checks, vẫn rẻ nhờ I8 keys-only:

1. **Ref-existence:** extract `[E###]` → verify tồn tại trong bundle → `unknownEvidenceReferences = 0`.
2. **Closed-world entity check:** mọi star/palace/mutagen/pattern name trong output phải thuộc key-set của bundle (vocab enumerable ~100 sao + 12 cung + 4 hóa + 64 cục) → invented entity ≈ check miễn phí.
3. **Evidence-type ↔ claim-scope compat:** claim động (hiện tại/tương lai) phải cite ≥1 `horoscope_fact`; claim natal chỉ cite `knowledge` (lore chung) → flag.
4. **Orphan-claim flag:** câu nêu chart entity mà không có `[E###]` → flag review (không auto-reject).

Post-stream: deterministic claim-extraction pass (split câu, map `[E###]` → span chứa nó) → lưu claim↔evidence pairs vào `InterpretationRun` — được auditability mà không trả giá streaming UX. Strict JSON output bị reject cho V1 (partial JSON không render được; endpoint của user có thể không support `response_format`).

UI render `[E001]` thành *"Căn cứ ▼"*.

## 13. `InterpretationRun` — immutable, reproducible

```json
{
  "id": "...",
  "chartSnapshotId": "...",
  "topic": "career",
  "targetDate": null,
  "contextComposerVersion": "v1",
  "evidenceBundleId": "...",
  "knowledgePacks": [{"id": "iztro-docs", "version": "...", "sha256": "pack.to_dict() hash"}],
  "promptVersion": "career-v1",
  "promptTemplateSha256": "...",
  "modelProvider": "our-openai-compatible",
  "modelName": "...",
  "providerModelVersion": "...",
  "decoding": {"temperature": 0.6, "topP": null, "seed": null, "maxTokens": null},
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
- **Split config** report vs chat (report: temp ~0.6, có evidence contract; chat: temp cao hơn chút, context nhẹ hơn).
- Model floor gợi ý ban đầu (benchmark quyết định — Gate E): Qwen3-32B-class open weights hoặc 4o-mini-class managed — cần đủ mạnh đọc zh + viết vi.

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

Baseline: adapt `Crazycreate/Numerology` prompts.ts (MIT), bỏ logic Bát Tự; giữ policies: không invent event, tách tendency/event, cite chart basis, không giấu mâu thuẫn, sectioned generation + shared cached prefix, caveats array, reviewed-flag cho knowledge data — **viết lại bằng tiếng Việt đúng register, không dịch nguyên văn zh prompts**.

Mixed-language context cần 3 thứ trong prompt: (a) instruction "đọc-hiểu tri thức zh rồi diễn đạt tiếng Việt tự nhiên — KHÔNG dịch sát câu"; (b) canonical glossary từ bundle (vi labels sẵn) + "dùng đúng tên trong bằng chứng"; (c) 2–3 exemplar đoạn vi register "thầy tử vi hiện đại". Post-pass deterministic normalize surface variants (Liêm Trinh/Liêm Chinh → canonical).

**Safety policy (system prompt, không rải rác):** trình bày là luận giải truyền thống/mệnh lý học, không phải chẩn đoán y khoa/tư vấn tài chính/pháp lý; health/investment/legal không được biến thành claim chuyên môn. **Cấm deterministic claims về tử vong/tai họa/tuổi thọ** (taboo văn hóa VN + rủi ro uy tín — vào rubric Gate E). UI: footer "mang tính tham khảo" + disclaimer mạnh hơn trong template topic Sức khỏe (Tật Ách) và Tài vận (Tài Bạch).

## 16. API surface (MVP cố ý nhỏ)

```text
POST /api/charts
GET  /api/charts/{id}
POST /api/charts/{id}/interpret     {topic} | {topic, target:{scope,year}}
POST /api/charts/{id}/chat          (sau vertical slice — optional V1)
GET  /api/charts/{id}/fortune/year/{year}   (anchor-date convention: mặc định Tết Âm lịch của năm đó; API validate target ≥ normalized birth — engine không check)
GET  /health                        (api + db; KHÔNG phụ thuộc AI)
GET  /health/dependencies           (AI dependency state)
GET  /s/{token}                     read-only chart view (share_token unguessable — growth/share khi chưa có auth; claim-on-signup sau)
POST /api/charts/{id}/compatibility {other_chart_id, mode: spouse|business}   — V1.1, đóng băng contract NGAY để Mode-1/2 không breaking (hợp bàn = top-3 feature VN)
```

SSE events: `metadata → evidence → delta* → done`; failure: `error` event + run marked failed — **không bao giờ** persist partial-as-complete.

### 16.1 Failure & validation semantics

- Model endpoint down/timeout → typed `502/503`, `InterpretationRun` status=`failed`.
- SSE mid-stream abort → `error` event; retry = **run mới** (không resume).
- Malformed output / grounding-reject → 1 deterministic repair retry rồi fail-run; log làm eval data.
- `POST /interpret` idempotency key `(chart_id, topic, target, prompt_version, model)` → dedupe double-click + replay stored run.
- Typed `422`: `leapMonth=true` trên tháng không nhuận (engine **silent-ignore** — phải pre-validate bằng leap-month table), ngày âm không tồn tại, solar year ngoài `1583–9999`, `timeIndex` ngoài `0–12`, `fortune target < birth`, birth trong tz divergence window thiếu `birthRegion`.

## 17. Database model (PostgreSQL, JSONB cho object nặng)

```text
birth_profiles          (anonymous-scoped V1 — bảng users thêm khi có auth, tránh dead schema)
raw_birth_inputs
normalized_birth_moments
engine_profiles
chart_snapshots         (+ share_token)
conversations
messages
evidence_bundles
interpretation_runs
```

Không normalize sao/cung thành hàng chục bảng quan hệ ở V1.

Compose V1 phải self-host thật: `migrate` service one-shot (`alembic upgrade head` on boot), postgres named volume + `pg_dump` backup note, reverse proxy (Caddy) tắt SSE buffering (`X-Accel-Buffering: no`), healthchecks + `depends_on`, `tzdata` dependency + startup assert `ZoneInfo("Asia/Ho_Chi_Minh")` (slim images có thể thiếu tzdata).

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
│       │   ├── contracts/      Pydantic models → OpenAPI (nguồn truth duy nhất)
│       │   ├── domain/         birth/ chart/ context/ evidence/ interpretation/
│       │   ├── infrastructure/ db/ xiztro/ llm/
│       │   ├── prompts/
│       │   └── settings.py
│       ├── tests/ alembic/ pyproject.toml
├── packages/
│   ├── contracts/              CanonicalChartDTO + DTOs — one-way codegen FastAPI OpenAPI → TS types (openapi-typescript); không 2 nguồn truth
│   └── knowledge/              overlay packs (sau)
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
| x-iztro pre-1.0, single-author | Pin wheel trong `uv.lock` + differential oracle CI + CanonicalChartDTO giữ swap sang JS iztro là bounded change + JSON/to_text contracts snapshot-guarded |
| VN timezone: 2 divergence windows (1954-10→1955-07, 1960-01→1975-06-12) — sai chart miền Bắc ~20,7 năm; `Asia/Hanoi` vắng khỏi tzdata rearguard | VN rule table versioned trong `vn-tst-v1` (không zoneinfo lookup) + `birthRegion` bắt buộc trong window + Gate A corpus ngày ranh |
| `leapMonth`/`is_leap_month` silent-ignore khi tháng không nhuận | Pre-validate bằng leap-month table → typed 422 |
| Citation laundering (invented entity + cite hợp lệ) | Closed-world entity check trong GroundingValidator (Gate C) |
| KnowledgePack chưa đủ deep (chỉ zh-CN, semantic dict) | ContextComposer + eval gates; RulePack/vi overlay chỉ khi eval chứng minh gap |
| True solar time VN edge cases | `vn-tst-v1` normalizer + boundary tests bắt buộc trước release |
| LLM hallucinate chart facts | Evidence-only policy + GroundingValidator 4-checks (ref-existence + closed-world + type↔scope + orphan flag) + claim-extraction audit (SPEC §12) |
| x-iztro footguns | `to_dict()` drop custom config → rebuild từ `engine_profiles`; name-addressing ambiguous → keys-only (I8); `horoscope()` không validate pre-birth → validate ở API layer |
| Model không biết Tử Vi | Eval harness Gate E đo trước khi ship; model choice theo benchmark, không cảm giác |
| Chất lượng zh-CN KnowledgePack chưa rõ (mới, community nhỏ) | Sample-review pack trước khi pin làm V1 pack duy nhất; Gate E terminology check |
| Fallback engine | `iztro-py` (pure Python, có vi-VN) tồn tại như contingency nếu x-iztro hỏng |
