# Council Review — Architecture V2

Council độc lập gồm 5 chuyên gia review `docs/SPEC.md` + `docs/IMPLEMENTATION_PLAN.md` trước khi khóa hướng đi. Mỗi review chạy trong một phiên Devin riêng, nhận cùng một brief (spec rút gọn + các yêu cầu cứng), và trả về verdict/issues/alternatives có cấu trúc.

## Thành phần council

| # | Lens | Trọng tâm |
|---|------|-----------|
| 1 | Ziwei domain / engine | x-iztro API thực tế vs spec, school coverage, VN-specific gaps |
| 2 | Principal architect | Monorepo split, contracts, versioning, deploy shape |
| 3 | LLM/agent engineer | Evidence-grounding, context budget, tool-calling, model strategy |
| 4 | Reliability/eval | Eval gates, differential oracle, reproducibility, failure modes |
| 5 | Product/VN domain | Đúng MVP cho thị trường VN, terminology, safety, hợp bàn |

## 1. Ziwei domain / x-iztro expert — ✅ completed (verified bằng code thật)

**Verdict:** ship with changes. Đã `pip install x-iztro==0.6.1`, introspect toàn API, và chạy differential thật vs `iztro@2.6.1` (8 natal cases: 太阳酉=平/七杀酉=旺, ageDivide=birthday, dayDivide 2 modes) → **0 divergence**.

**Findings đã apply vào SPEC/PLAN:**

| # | Severity | Finding | Đã sửa ở |
|---|----------|---------|----------|
| 1 | high | Language strategy: tạo chart `language='vi-VN'` (verified: không ảnh hưởng computation) + explicit `KnowledgePack.builtin('zh-CN')` cho AI context → evidence khớp UI, prose vẫn zh | SPEC §7, PLAN Phase 3 |
| 2 | high | `chart.to_dict()['config']` **drop** custom mutagens/brightness → ChartConfig luôn rebuild từ `engine_profiles` | SPEC §3, PLAN Phase 3 + Phase 8 eval case |
| 3 | medium | `horoscope(target_date)` nhận solar date đầy đủ, 6 scopes/1 call, không validate pre-birth → anchor convention + API validation + scope selection | SPEC §9/§16, PLAN Phase 7 |
| 4 | medium | Name-based addressing ambiguous → keys-only invariant (I8 mới) | SPEC §1.1 I8 |
| 5 | medium | `timeIndex` có 13 slot (0–12); TST shift cả date lẫn double-hour → `(correctedSolarDate, timeIndex)` + boundary eval cases | SPEC §4.3/§5, PLAN Phase 2 |
| 6 | low | `yearly_list()` bắt buộc decadal ordinal/palaceKey; `monthly_list` trả 14 items năm nhuận | DONORS notes |

**Bonus verified:** engine có ZERO tz/longitude/DST/TST handling → normalizer đúng chỗ; per-chart config (không global singleton như JS iztro) → multi-profile tốt hơn cả upstream; `patterns()` 64 rules + `flanking_palaces` (夹宫) + `decadal_list/yearly_list/monthly_list` + reverse lookup + plugins. i18n vi-VN HOÀN CHỈNH cho chart labels; `vi-VN` KnowledgePack raise IztroError (claim cũ đúng). Dataset 518,400 vs state space thật ~561,600 (13 time indices) — off critical path.

**Alternatives bị reject:** JS iztro làm engine chính (global config singleton, thiếu patterns/knowledge/reverse layers); tự port engine từ Renhuai (~weeks, phải tự chứng minh correctness).

## 2. Principal architect — ✅ completed (verified hands-on: introspected wheel, cloned Renhuai, checked tzdb)

**Verdict:** ship with changes — decomposition đúng, x-iztro bet verified; thiếu vài contract fields quyết định correctness với user VN thật + vài chỗ over-scope cần trim.

**Findings đã apply:**

| # | Severity | Finding | Đã sửa ở |
|---|----------|---------|----------|
| 1 | high | Thiếu lunar input path (âm lịch) — gap lớn nhất cho VN; `by_lunar(is_leap_month)` native đã verified | SPEC §4.1, PLAN Phase 2 |
| 2 | high | Thiếu `birthRegion` → sai chart miền Bắc 1960–1967 (tzdb merged Asia/Saigon → UTC+08 cho 1960→1975-06-12; Hà Nội +07 tới 1968) → rule table theo region + ghi `tzKey/tzdataVersion/resolvedOffset` | SPEC §4/§5, PLAN Phase 2 |
| 3 | high | Quyền sở hữu day-roll Tý muộn chưa rõ → double-roll bug: normalizer xuất `(date, timeIndex)` verbatim, roll thuộc `dayDivide` trong engine | SPEC §5, PLAN Phase 2 |
| 4 | high | ChartDTO boundary chưa định — x-iztro JSON sẽ leak vào API/DB → CanonicalChartDTO keyed `*_key`, `schemaVersion`, 1 mapper, OpenAPI→TS one-way codegen, import-lint | SPEC §6/§18, PLAN Phase 1/3 |
| 5 | medium | Deploy self-host thiếu: migrate service, volume+backup, SSE-safe proxy, healthchecks, `tzdata` assert | SPEC §17, PLAN Phase 0/2 |
| 6 | medium | Over-scope: cắt `packages/ui`, bỏ bảng `users`, codegen one-way, `prompt_version` là constant | SPEC §17/§18, PLAN Phase 0.5 |
| 7 | low | DST machinery thừa (tzdb: 0 DST periods cho VN) — công việc thật là +08 window | SPEC §5 |
| 8 | low | `timeUnknown` flag thêm sớm tránh migration | SPEC §4.1 |

**Alternatives đánh giá:** Next.js fullstack + JS iztro (viable, rẻ hơn cho pure web MVP nhưng phải tự port 64-pattern judgement + KnowledgePack + to_text — rejected vì engine-native Python); FastAPI serving static SPA (giảm 1 service, mất SSR không quan trọng — giữ compose như spec'd cho dev UX). Verdict cuối: giữ split Next.js+FastAPI.

## 3. LLM/agent systems engineer — ✅ completed (cài x-iztro + clone donors, verify bằng code)

**Verdict:** ship with changes — pipeline đúng hướng, đúng donor; GroundingValidator spec cũ chỉ check ref-existence là chưa đủ giữ promise "auditable".

**Findings đã apply:**

| # | Severity | Finding | Đã sửa ở |
|---|----------|---------|----------|
| 1 | high | GroundingValidator nâng lên 4 checks: + closed-world entity (vocab enumerable ~100 sao/12 cung/4 hóa/64 cục nhờ I8), evidence-type↔claim-scope compat, orphan-claim flag | SPEC §12, EVAL Gate C |
| 2 | medium | Evidence-ID collision giữa nhiều context calls → allocator per run/conversation, namespaced `c1.E003` | SPEC §11, PLAN Phase 5 |
| 3 | medium | Knowledge excerpt policy — KP intros là essay zh 400–800+ chars, dump gây style-bleed → aspect-scoped excerpt ~150–300 chars | SPEC §9, PLAN Phase 5 |
| 4 | medium | `timeUnknown` flow: provisional chart + caveat V1; hour-inference deferred (donor `hourinfer.ts`) | SPEC §4.1 |
| 5 | medium | Mixed-language context cần: internalize-don't-translate instruction + canonical glossary + 2–3 exemplar đoạn vi; post-pass normalize variants | SPEC §15 |
| 6 | low | `lunar_date` giữ chữ Hán số mọi language → vi formatter; `astrolabe_to_prompt` KHÔNG tồn tại trên Python 0.6.1 | SPEC §7, PLAN Phase 5 |
| 7 | low | Overview = compact full-chart render (`to_text` ~7.5k chars rẻ); topics = subgraph | SPEC §9 |

**Alternatives đánh giá:** strict JSON `claims[{text,evidence_ids}]` → REJECT V1 (phá SSE streaming, endpoint support không đảm bảo) — thay bằng post-stream claim-extraction; vi overlay pack pre-MVP → defer theo Gate E; whole-chart dump mọi topic → reject (overview thì dùng compact full chart).

**Model strategy:** floor Qwen3-32B-class open weights hoặc 4o-mini-class managed; temp ~0.6–0.7; split report/chat config; fine-tune chỉ khi Gate E thấy systematic register failure.

## 4. Reliability/eval lead — ✅ completed (verify trên box: tzdata rearguard thật thiếu `Asia/Hanoi`; zdump checked)

**Verdict:** ship with changes — reliability layer có lỗ hổng thực; sửa xong thì "auditable" là claim thật.

**Findings đã apply:**

| # | Severity | Finding | Đã sửa ở |
|---|----------|---------|----------|
| 1 | **blocker** | Quy tắc tz miền Bắc sai (council-2 nói "Hà Nội +07 tới 1968" — SAI): Hà Nội +08→1954-10 (ngày không rõ → flag ambiguous), +07 liên tục sau; **2 divergence windows**: 1954-10→1955-07-01 và 1960-01-01→1975-06-12 (~20,7 năm); Sài Gòn quirk +07 1955→1959 + blip 1h | SPEC §5, EVAL Gate A |
| 2 | high | `Asia/Hanoi` **không tồn tại** trong tzdata rearguard (Ubuntu/Debian + PyPI wheel — verified trên box) → VN rule table là versioned data trong `vn-tst-v1`, không lookup zoneinfo | SPEC §5, PLAN Phase 2 |
| 3 | high | Ref-existence không đủ — *citation laundering* + misattribution → entity-level check (closed-world) + entailment vào Gate E | SPEC §12, EVAL Gate C |
| 4 | high | Reproducibility contract thiếu pins → canonical JSON spec, hash trên CanonicalChartDTO, + normalizer_version/dto_schema_version trong chartHash, prompt/pack **content** hash, decoding params, provider model version; goal = "reproduce decision inputs" chứ không byte-for-byte | SPEC §6/§13 |
| 5 | high | Failure semantics chưa spec → typed 502/503 + no partial persist, SSE abort = new run, 1 repair retry, idempotency key, typed 422s (leapMonth silent-ignore của engine phải pre-validate) | SPEC §16.1, PLAN Phase 7 |
| 6 | medium | Evidence ID ordering cần deterministic (stable sort type/palace_key/entity_key) nếu không contextHash không ổn định | SPEC §6 |
| 7 | — | Gate B rescope adapter-level (upstream đã prove engine parity) + 2-tier: CI boundary corpus <1ph + nightly 20–50k | EVAL Gate B |

**Bonus verified:** `fix_leap` carry-over cần 4 điều kiện (leap thật + fix_leap + day>15 + hour≠12); `is_leap_month` silent no-op; solar range 1583–9999; frozen dataclasses (GIL → scale by processes); iztro 2.6.0+ additive only.

**Alternatives:** SQLite-thay-Postgres (hợp lệ nếu single-user-forever; giữ Postgres vì multi-user path) — **decision theo product shape**; VN-tz-table-as-data → khuyến nghị, đã áp dụng; Gate B two-tier → áp dụng.

## 5. Product/domain strategist (VN market) — ✅ completed (verify i18n files, tzdb backzone, competitors)

**Verdict:** ship with changes — cần vá 4 lỗ hổng đặc thù VN trước khi đóng băng V1.

**Findings đã apply:**

| # | Severity | Finding | Đã sửa ở |
|---|----------|---------|----------|
| 1 | high | Glossary zh→vi là V1 artifact bắt buộc (sinh từ i18n table vi-VN của x-iztro — chuẩn Hán-Việt: Mệnh/Tử Nữ/Nô Bộc/Kình Dương/Triệt Không/Lai Nhân) → inject prompt + validator flag lệch glossary | SPEC §7, PLAN Phase 5, EVAL Gate E |
| 2 | high | `birthRegion` timezone — độc lập confirm council-4: Bắc +7, Nam +8 trong windows; `Asia/Hanoi`/`Asia/Saigon` ở backzone, stock tzdb không thấy; cohort bị ảnh = cha mẹ 50–65 — đúng demographic chính | SPEC §5 (đã fix bởi #4) |
| 3 | medium | Hợp bàn top-3 feature VN → giữ defer nhưng **freeze API surface ngay** (`POST /charts/{id}/compatibility`, `compare_profiles` trong Mode-2) | SPEC §16, PLAN Phase 2 |
| 4 | medium | Đại vận chưa first-class → current+next đại vận vào overview context (gần như free) | SPEC §9, PLAN Phase 5 |
| 5 | medium | `share_token` + `GET /s/{token}` — kênh growth số 1 khi chưa có auth | SPEC §16/§17, PLAN Phase 2 |
| 6 | medium | Safety: cấm deterministic claims tử vong/tuổi thọ + disclaimer footer/topic | SPEC §15, EVAL Gate E |
| 7 | low | UI checklist VN: Tuần/Triệt Không, Ngũ hành cục, đại hạn tuổi mụ, giờ picker theo chi | PLAN Phase 4 |

**Alternatives:** compatibility-first wedge → không pivot (giữ thứ tự, freeze API V1.1); chart-render-only → fallback nếu Gate B/C trượt; chat-first → reject (mất auditable moat); dataset→canned text → reject (generic, đúng điểm yếu cần đánh bại).

**Note:** iztro-py (pure Python, vi-VN) tồn tại → fallback engine contingency. Chất lượng zh-CN pack cần sample-review trước pin.

## Tổng hợp

**Quyết định cuối: giữ nguyên hướng kiến trúc V2 (x-iztro canonical + FastAPI monolith + Next.js + Postgres + own LLM endpoint), không có hướng đi nào của council thắng thế được nó.** 5/5 member độc lập verify cùng kết luận "ship with changes" — không ai đề xuất pivot.

Các alternative directions đã cân và loại:

| Alternative | Từ | Verdict |
|---|---|---|
| Next.js fullstack + JS iztro (bỏ Python) | #2 | Rejected — phải tự port 64-pattern judgement + KnowledgePack + to_text; eval/dataset work là Python-shaped |
| JS iztro làm engine chính | #1 | Rejected — global config singleton, thiếu layers x-iztro native |
| Tự port engine từ Renhuai | #1 | Rejected — weeks, phải tự chứng minh correctness |
| SQLite thay Postgres | #4 | Giữ Postgres (multi-user path) — revisit nếu V1 là single-user-forever |
| Strict JSON claims output | #3 | Rejected V1 (phá SSE) — post-stream claim-extraction thay thế |
| Compatibility-first / chat-first / canned-text | #5 | Rejected — giữ thứ tự spec |
| vi KnowledgePack pre-MVP | #3/#5 | Defer theo Gate E score |
| VN-tz-table-as-data (thay zoneinfo) | #4 | **ÁP DỤNG** — bắt buộc vì Asia/Hanoi vắng khỏi tzdata triển khai |
| Gate B two-tier (CI corpus + nightly) | #4 | Áp dụng — adapter-level differential |

**Thay đổi material so với spec gốc sau council:** language strategy đảo (chart vi-VN + knowledge zh-CN explicit); I8 keys-only; ChartConfig rebuild rule; VN tz rule table + birthRegion + 2 divergence windows; lunar input path native; GroundingValidator 4-checks; reproducibility contract (content hashes + canonical JSON + decoding params); failure semantics + idempotency + typed 422s; glossary-vi V1 artifact; đại vận trong overview; share_token; freeze compatibility API V1.1; scope trims (packages/ui, users table, DST machinery).
