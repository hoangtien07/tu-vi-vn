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

- [x] Monorepo skeleton theo `SPEC.md` §18: `apps/web` (Next.js 15, TS, Tailwind, pnpm), `apps/api` (FastAPI, Python 3.12, uv, pyproject), `packages/`, `eval/`, `infra/`, `scripts/`, `docs/`
- [x] `infra/docker-compose.yml`: `web`, `api`, `postgres` (16), `migrate` (one-shot `alembic upgrade head`). Không Redis. Postgres named volume + backup note (`pg_dump`); reverse proxy (Caddy) tắt SSE buffering (`X-Accel-Buffering: no`); healthchecks + `depends_on`.
- [x] `infra/env/.env.example`: `DATABASE_URL`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, `AI_TIMEOUT_SECONDS`
- [x] `GET /health` (api+db), `GET /health/dependencies` (AI — không block app health)
- [x] ruff + mypy strict-lite cho api; eslint + tsc cho web; CI chạy lint+typecheck+pytest

## Phase 1 — Contracts & persistence (commit 2, 4)

- [x] `domain/birth/contracts.py`: `RawBirthInput` (gồm `calendar`, `leapMonth`, `birthRegion`, `timeUnknown`), `CivilBirthMoment`, `NormalizedBirthMoment` (gồm `tzKey`, `tzdataVersion`, `resolvedOffsetMinutes`) — Pydantic theo SPEC §4
- [x] `EngineProfile` + seed `iztro-default-v1` (SPEC §3)
- [x] Alembic init; bảng: `birth_profiles` (anonymous V1, không `users` table), `raw_birth_inputs, normalized_birth_moments, engine_profiles, chart_snapshots, conversations, messages, evidence_bundles, interpretation_runs` (JSONB cho chart/evidence)
- [x] `packages/contracts`: CanonicalChartDTO + DTOs; contract codegen **one-way** FastAPI OpenAPI → TS (openapi-typescript) — không maintain 2 nguồn
- [x] `chart_hash = sha256(canonical_json(normalized) + engine_version + profile_content + normalizer_version + dto_schema_version)`; canonical JSON = sorted keys/UTF-8/no-whitespace; chart snapshot immutable; evidence ordering deterministic (sort type/palace_key/entity_key)

## Phase 2 — Birth normalization (commit 5)

- [x] `domain/birth/calendar.py`: solar/lunar → `CivilBirthMoment`; path lunar dùng `by_lunar(is_leap_month)` native của x-iztro (verified)
- [x] **Không** DST machinery cho VN (tzdb: 0 DST). **VN rule table** versioned-data trong `vn-tst-v1` (không zoneinfo — `Asia/Hanoi` vắng khỏi tzdata rearguard): Hà Nội +08→1954-10 (flag ambiguous), +07 sau; Sài Gòn +07 1955-07-01→1959-12-31, +08 1960-01-01→1975-06-12 23:00; divergence windows (1954-10→1955-07, 1960-01→1975-06-12) yêu cầu `birthRegion`
- [x] **Tý muộn ownership:** normalizer xuất `(correctedSolarDate, timeIndex)` verbatim — day roll thuộc `dayDivide` trong engine config, normalizer không tự roll (tránh double-roll). Boundary test 23:00/00:00 bắt buộc
- [x] `tzdata` dependency + startup assert `ZoneInfo("Asia/Ho_Chi_Minh")`
- [x] `domain/birth/normalizer.py` `BirthTimeNormalizer` Protocol + impl `vn-tst-v1`: timezone (IANA) → DST/historical VN → longitude correction → equation of time → date rollover → `NormalizedBirthMoment.timeIndex`
- [x] Reference đọc: `Renhuai lib/ziwei/true-solar-time.ts` (MIT). **Không** copy `dst-cn.ts` làm default VN.
- [x] Boundary tests bắt buộc: `00:00/00:59/01:00/22:59/23:00/23:59`, index 0 vs 12 (晚子时 + `dayDivide`), correction qua ngày trước/sau, thiếu tọa độ, lunar→solar + `is_leap_month` (pre-validate leapMonth bằng leap-month table → 422), tháng nhuận, ±30 phút quanh mọi hour boundary, ranh giới Tết, longitude cực trị VN (Móng Cái ~107.9°E / Cà Mau ~104.8°E), ngày ranh tz VN `1947-04-01, 1954-10, 1955-07-01, 1959-12-31/1960-01-01, 1975-06-12/13` × `birthRegion`
- [x] `NormalizedBirthMoment` persist cặp `(correctedSolarDate, timeIndex 0–12)` — engine input (SPEC §4.3)
- [x] `POST /api/charts` trả `{id, birth:{raw, normalized}, chart, shareToken}`; `chart_snapshots.share_token` (unguessable) + `GET /s/{token}` read-only view (share/growth khi chưa có auth)
- [x] Freeze contract V1.1 ngay trong API surface: `POST /api/charts/{id}/compatibility {other_chart_id, mode: spouse|business}` (stub 501 OK — hợp bàn top-3 feature VN, không breaking sau); giữ `compare_profiles` trong Mode-2 tools

## Phase 3 — Engine adapter (commit 3)

- [x] `infrastructure/xiztro/engine.py` — `XiztroEngine` implement `ZiweiEngine` Protocol:

```python
class ZiweiEngine(Protocol):
    def cast_chart(self, birth: NormalizedBirthMoment, profile: EngineProfile) -> CanonicalChart: ...
    def get_horoscope(self, chart: CanonicalChart, target: date) -> HoroscopeContext: ...
    def get_surrounded_context(self, chart: CanonicalChart, palace_key: str) -> DomainContext: ...
```

- [x] Chỉ file này `import x_iztro`. `astro.by_solar(normalized_date, time_index, gender, language="vi-VN", config=...)` — vi-VN labels khớp UI (verified: language không ảnh hưởng computation); knowledge lookup truyền explicit `KnowledgePack.builtin("zh-CN")`
- [x] **Hard rule:** `ChartConfig` rebuild từ `engine_profiles` row — không rehydrate từ `chart.to_dict()['config']` (drop mutagens/brightness). Mọi addressing bằng keys (`soulPalace`...), không translated names (I8)
- [x] `CanonicalChartDTO` (SPEC §6): meta/palaces/patterns/engine keyed bằng `*_key`, `schemaVersion`; FE chỉ ăn DTO của ta, không leak Python object. CI import-lint: cấm `import x_iztro` ngoài `infrastructure/`
- [x] `GET /api/charts/{id}`
- [x] Fixture regression test: input + profile → expected facts (命宫/身宫/chính tinh/tứ hóa/patterns), không chỉ snapshot full JSON
- [x] `scripts/differential/` (CI): x-iztro vs JS iztro@2.6.1 trên N random + boundary cases; classify mismatch (bug/school/config/normalization)

## Phase 4 — Chart UI (commit 6)

- [x] Port chọn lọc từ Renhuai (MIT): `ChartBoard`, `PalaceCell`, `BirthForm`, `TimeNav` cơ bản → `apps/web/features/chart/`
- [x] Palace cell checklist VN: Tuần Không, Triệt Không, Ngũ hành cục (Thủy nhị cục...), đại hạn range theo **tuổi mụ**; birth form giờ sinh picker theo chi (Tý/Sửu...) + âm lịch + nhuận + `birthRegion`
- [x] Adapter `CanonicalChartDTO → RenhuaiChartViewModel` trong `features/chart/adapters/` — assumption của Renhuai không nhiễm vào API contract
- [x] Trang `/` (birth form), `/chart/{id}` (12 cung)

## Phase 5 — Knowledge + Context + Evidence (commit 7, 8)

- [x] `infrastructure/xiztro/knowledge.py` — `KnowledgeRegistry`: `KnowledgePack.builtin("zh-CN")` load 1 lần, `version_info()`
- [x] Knowledge excerpt policy: ~150–300 chars/sao/aspect từ `StarEntry.attributes` — không dump essay zh nguyên văn; kind `knowledge` được đánh dấu lore (không phải chart fact)
- [x] `packages/knowledge/glossary-vi.md` — sinh ~200–400 dòng từ i18n table vi-VN của x-iztro (script `scripts/gen_glossary.py`); inject prompt + validator flag surface-form lệch
- [x] Overview context + summary đại vận hiện tại & kế tiếp
- [x] vi lunar-date formatter (chart `lunar_date` luôn chữ Hán số → render `'17/7 âm lịch 2000'`)
- [x] `domain/context/composer.py` — `ContextComposer.compose(chart, topic, target) -> ComposedContext`; `TOPIC_POLICY` (SPEC §9); overview = broad natal, topic khác = palace + tam phương tứ chính + patterns + mutagens liên quan
- [x] `domain/evidence/builder.py` — `EvidenceBuilder`: `ComposedContext → EvidenceBundle` với stable IDs `E001...` — allocator per InterpretationRun/conversation (không reuse E001 giữa calls)
- [x] Tests: career phải chứa career palace + 三方四正 + relevant patterns; career+2028 phải chứa thêm horoscope 2028; không dump toàn bộ chart

## Phase 6 — LLM pipeline (commit 9, 10)

- [x] `infrastructure/llm/openai_compatible.py` — `LLMProvider` Protocol + httpx impl, env config (SPEC §14)
- [x] `app/prompts/` theo SPEC §15 (adapt Crazycreate, bỏ Bát Tự, giữ evidence/anti-invent policies + safety VN)
- [x] `PromptRenderer`: topic + ComposedContext + EvidenceBundle → `messages[]`
- [x] `POST /api/charts/{id}/interpret` → pipeline: ChartSnapshot → ContextComposer → EvidenceBuilder → PromptRenderer → LLMGateway → GroundingValidator → InterpretationRun → SSE (`metadata, evidence, delta, done`)
- [x] `GroundingValidator` 4 checks (SPEC §12): ref-existence, closed-world entity (vocab keys từ bundle), evidence-type↔claim-scope compat, orphan-claim flag — vẫn deterministic
- [x] Post-stream claim-extraction pass → claim↔evidence pairs lưu vào `InterpretationRun`
- [x] InterpretationRun persist đủ version metadata (SPEC §13)
- [x] UI: interpretation panel 5 tabs + "Vì sao?" evidence drawer (render `Căn cứ ▼`, không raw `[E###]`)
- [x] Split LLM config report vs chat; `timeUnknown` → provisional chart + caveat trong evidence/output
- [x] Prompt safety: cấm deterministic claims tử vong/tai họa/tuổi thọ; footer "mang tính tham khảo" + disclaimer mạnh cho topic Sức khỏe/Tài vận

## Phase 7 — Yearly fortune + chat (commit 11)

- [x] `GET /api/charts/{id}/fortune/year/{year}` — `chart.horoscope(target_date)` anchor = Tết Âm lịch năm đó (convention ghi trong SPEC §16); API validate `target_date ≥ normalized birth` (engine không check); ContextComposer chỉ chọn scopes cần (yearly+decadal+age)
- [x] Failure semantics theo SPEC §16.1: typed 502/503 + run failed (không persist partial); SSE abort → error event + retry = run mới; grounding-reject → 1 repair retry; `/interpret` idempotency key `(chart_id, topic, target, prompt_version, model)`; typed 422s (leapMonth, lunar day không tồn tại, solar year ngoài 1583–9999, thiếu birthRegion trong divergence window)
- [x] `interpret` với `{topic, target:{scope:"yearly", year}}`
- [x] `/api/charts/{id}/chat` (simple): system + domain context hiện tại + last N turns; chat không được thay thế chart context
- [x] `Conversation`/`Message` persist

## Phase 8 — Eval gates (commit 12)

- [x] `eval/` cases: `birth-normalization.json`, `chart-regression.json`, `topic-routing.json`, `grounding.json`, `interpretation.json` (~50 cases trước, không hàng nghìn)
- [x] Gates A–E theo `EVALUATION.md`; fail gate → block release

## Sau V1 (Phase 2+ — KHÔNG làm trước khi V1 done + benchmark)

```text
Auth, multi-profile, **compatibility (hợp bàn) = V1.1 committed**, K-line, share cards, PDF,
流月/流日/流时, Vietnamese KnowledgePack overlay, InterpretationRulePack,
Dataset v3 mining (eval/knowledge/fine-tune), RAG (chỉ nếu eval chứng minh cần),
tool-calling chat mode (4 semantic tools), model routing theo task
```

Gate trước Phase 2: chạy 20–30 charts × 5 topics qua vài candidate models; so sánh grounding/specificity/consistency/VN quality/latency/cost → quyết định đầu tư tiếp vào model / prompts / RulePack / vi pack / dataset mining.

**Gate E đã chạy (2026-09-24, `eval/bench/`):** 24 charts × 5 topics = 120 interpret runs qua `gemini-3.8-flash` — LLM-judge rubric specificity/relevance/consistency 5.00, VN quality 4.97, overclaim 0; residual grounding fail 5/120 (genuine catches: cite sai loại evidence, bịa sao — zero-tolerance hoạt động đúng). **Quyết định: gemini-3.8-flash là model V1.** Benchmark xoay quanh 1 model — nếu cần so sánh thêm candidate (flash-lite/pro tier), chạy lại `eval/bench/run_bench.py` với `AI_MODEL` khác.

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

## Phase 0.5 — scope trims (áp dụng ngay, đừng build thừa)

- Bỏ `packages/ui` khỏi V1 (không có consumer thứ 2 — UI sống trong `apps/web`)
- Không tạo bảng `users` ở V1 (auth deferred; `birth_profiles` anonymous-scoped)
- `prompt_version` là file constant, không phải bảng
- Mode-2 tool-calling: chỉ giữ trong spec, không scaffold

Gate phụ trong Phase 8: ≥1 eval case chạy **non-default mutagen profile** end-to-end (ChartConfig rebuild path — verified footgun SPEC §3).

## Definition of Done — Vertical Slice V1

- [x] Birth profile nhập được; raw/civil/normalized đều persisted
- [x] x-iztro cast chart deterministic; engine version + profile persisted; snapshot immutable
- [x] UI 12 cung render từ `CanonicalChartDTO`
- [x] 5 topics (overview/career/wealth/love/health) chạy được; career+year chạy được
- [x] KnowledgePack vào context không qua RAG; ContextComposer selective
- [x] EvidenceBundle tồn tại trước khi gọi LLM; `[E###]` validated
- [x] LLM chỉ qua `AI_BASE_URL` configurable; SSE streaming; "Vì sao?" xem được evidence
- [x] Conversation + InterpretationRun lưu local
- [x] Không runtime request nào tới Iztro/Renhuai
- [x] `docker compose up` chạy được toàn bộ trừ AI endpoint (config)
- [x] Critical deterministic tests pass

## V1.1 hardening log (post-audit)

- [x] Temporal scope contract: `InterpretTarget{scope,year,month?,day?}` — scope
  khai báo tường minh, không suy từ `target_date`. Gate D sửa + tr-012/013.
- [x] Gate E tách E1 static (target=None) / E2 yearly (scope=yearly y=2028);
  namespace per run → 120/120 fresh, replay=0; latency tính fresh-only.
- [x] Grounding fixes từ corpus đóng băng: mutagen mọi cung vào bundle,
  entity whitelist trong prompt + repair, bỏ `tương lai` khỏi temporal regex,
  scan entity bỏ phần boilerplate "Lưu ý" + tên trường phái,
  parser nhận citation `[E001, E007]` (đây là nguyên nhân chính của
  "nhận định vận hạn thiếu horoscope_fact").
- [x] E1 static: **120/120 done, 0 fail** — `eval/bench/reports/gate-e-static-20260924-072822.md`.
- [ ] E2 yearly: **deferred** — key Gemini hết credit (402 giữa chừng;
  65/68 fail là llm_upstream, không phải grounding; phần chạy được trước
  đó chỉ còn ~3 grounding residual do citation parser bug — đã fix).
  Rerun khi có AI budget: `run_bench.py --suite yearly --year 2028`.
- [x] Human spot-check pack 24 outputs —
  `eval/bench/reports/spotcheck-static-20260924-072822.md`.
- [x] Release hygiene: MIT LICENSE + THIRD_PARTY_NOTICES + README status.

## v0.4 log — knowledge tournament

- [x] `KNOWLEDGE_PACK` env (builtin|none|path) → `KnowledgeRegistry.configure`;
  `none` ablation (excerpts → None, synthetic version_info); `/health` exposes
  `knowledgePack` id.
- [x] `eval/packs/` + schema README + `vn-seed-v1.json` (58 VN entries mined từ
  cited entity keys trong `eval/bench/reports/`).
- [x] `eval/tournament/run_tournament.py` — spawn uvicorn per variant trên
  shared DB → run_bench subprocess → comparison report; `--smoke` không cần LLM.
- [x] First tournament run (subset — 4 charts × 5 topics × 3 variants = 60
  fresh runs qua swe-2 shim): `none` 20/20 0-fail · `builtin` 19/20 1-fail ·
  `vn-seed-v1` 20/20 0-fail. Judge off → rubric vacuous.
  **Decision: giữ `builtin`** — vn-seed-v1 pass gate nhưng không thắng ablation
  `none`; cần full corpus + judge trước khi đổi pack.
  `eval/tournament/reports/20260925-021850/tournament-20260925-021850.md`
- [ ] Full 24-chart tournament + judge — rerun khi có inference budget lớn hơn.

## v0.5 log — K-line temporal visualization

- [x] `docs/SPEC_KLINE.md` — dải K-line vận trình: một glyph/lưu niên trong
  đại hạn, chỉ facts deterministic (tứ hóa theo thứ tự Lộc·Quyền·Khoa·Kỵ,
  cung lưu mệnh, can chi); cố ý không có "điểm vận" scalar.
- [x] `GET /api/charts/{id}/temporal/decade?year=` — decade boundary tìm
  bằng probe `decadal.index` (không suy từ tuổi mụ); `ageRange` từ
  `palaces[i].decadal.range` của snapshot. Fixes: natal palace label
  (scope `palaceNames` là layout rebase — luôn "Mệnh"), probe bound
  y<1583/y>9999, sticky `failed` + stale decade trên FE.
- [x] `KlineStrip` trên Time Navigator — chip tứ hóa theo hóa
  (Lộc/Quyền/Khoa/Kỵ), cung lưu mệnh, prev/next decade; click → đổi năm.
- [x] E2E browser check — recording + screenshots OK, zero LLM call khi
  render strip (API log chỉ temporal/decade + temporal + events).

## v0.5-mining log — dataset mining → vn-mined-v1 (SPEC_V05)

- [x] D1 `eval/mining/mine.py` — 720 gz JSONL / 518,400 samples qua
  `mp.Pool`; drift filter = re-cast bằng `iztro-default-v1` (drift 0.12%
  → drop 636; castErrors 2520; 515,244 kept). Attribution: phrase →
  star/pattern/palace + topic-palace majors; composite
  palaceStar/mutagenStar parked (schema chưa có chỗ).
- [x] D2 `eval/mining/pack.py` → `eval/packs/vn-mined-v1.json` —
  top-5/entity, boilerplate + >50% template-share + near-dup filters;
  zh→vi qua `AI_BASE_URL` (reasoning off); 58 entries (33 stars /
  13 patterns / 12 palaces), 243 phrases dịch; curated VN names;
  `patterns[].quotes` đúng field registry đọc.
- [x] D3 smoke tournament (reports/20260925-073219) — 3 variants ×
  4 charts × 5 topics qua swe-2 shim: 60/60 done, 0 grounding fails;
  không tách được ở coverage này + judge=off.
- [ ] D4 judged gate I24 (beat builtin AND none, 24 charts + --judge) —
  **chờ budget** (~360 turns qua worker; subset lớn hơn cũng được nếu
  cần signal trung gian). Pack giữ candidate, KHÔNG default.

## DO NOT (đưa vào mọi implementation prompt)

```text
LangGraph / agent frameworks, Redis, Celery, Kafka, vector DB, embeddings,
RAG, process Dataset v3, fine-tune, microservices, hosted Iztro API,
iztro-ziwei-v3 runtime, LLM tính lá số, fork nguyên Renhuai làm architecture,
duplicate x-iztro domain logic, WebSocket, vendor AI SDK
```
