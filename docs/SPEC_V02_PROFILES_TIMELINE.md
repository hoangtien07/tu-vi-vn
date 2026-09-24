# SPEC v0.2 — Profiles + Time Navigator + Reading Library

Trạng thái: draft → review → implement. Freeze scope: **không** RAG, không fine-tune, không đụng engine, không auth đầy đủ (auth → v0.3). Mục tiêu: biến reasoning engine thành sản phẩm có lý do quay lại — profile-centric + temporal navigation deterministic-trước, AI on-demand sau.

## 1. Product model

```
MY PROFILES                     TIME NAVIGATOR (trên 1 profile)
  Tiến / Người yêu / Mẹ           Đại hạn 33–42
    │            │                2025 2026 [2027] 2028 2029
    └──── Hợp bàn ◄── picker              T1 T2 [T3] T4 …
                   │                            1 2 [3] 4 …
            POST /api/compatibility                 │
                                          deterministic temporal facts
                                                  │
                                          [Luận tổng quan] → interpret SSE
```

Invariants từ AGENTS.md giữ nguyên. Bổ sung:

- **I9 — Navigation deterministic trước, AI sau.** Mở Time Navigator không gọi LLM; LLM chỉ chạy khi user bấm topic cụ thể.
- **I10 — TemporalTarget là contract duy nhất.** Không pipeline riêng theo scope; mọi temporal interpret đi qua `InterpretTarget` + `temporal_scopes_for` đã có.
- **I11 — Deterministic temporal facts phải trace được về chart.** Output navigator = `horoscope_fact` + `chart_fact` items tái sử dụng từ composer — không format string ad-hoc.
- **I12 — Profile chứa tham chiếu chart, không duplicate birth.** `profile.birthProfileId` → `ChartSnapshot`; sửa giờ sinh = chart mới (immutable chain).

## 2. Data model

```python
class Profile(Base):
    id: str = "pf_" + uuid4hex
    owner_key: str = "local"        # v0.2 single-tenant; v0.3 auth gắn user id
    display_name: str               # "Mẹ", "Người yêu", …
    relationship: str | None        # free-form enum: self/partner/mother/father/child/friend
    birth_profile_id: str           # FK → chart_snapshots.birth_profile_id (latest chart)
    chart_snapshot_id: str          # FK → chart_snapshots.id — pin chart hiện tại
    visibility: Literal["private", "shared-link"] = "private"
    created_at / updated_at
```

- `profile.chart_snapshot_id` pin snapshot — temporal facts luôn nhất quán với chart đã lưu.
- `owner_key` default `"local"` cho self-hosted; spec KHÔNG thêm auth trong v0.2 (capability-URL đã chấp nhận ở V1). v0.3 đổi sang user thật.
- Birth form submit → tạo `ChartSnapshot` như hiện tại → `POST /api/profiles` bọc chart đó thành profile (display_name bắt buộc).

## 3. TemporalTarget (đã có — formalize)

`InterpretTarget {scope: yearly|monthly|daily, year, month?, day?}` + `target_anchor()` + `temporal_scopes_for()` đã đúng contract:

- yearly → decadal + yearly + age
- monthly → + monthly
- daily → + daily

v0.2 chỉ mở rộng validation: `year` range hợp lý (birth→birth+120), `month` 1–12, `day` theo tháng. Không tạo scope mới. `natal`-only interpret vẫn `target=None`.

## 4. Endpoint mới — deterministic temporal facts

```
GET /api/charts/{chart_id}/temporal?year=2028&month=5&day=18
```

Trả `TemporalFacts` — KHÔNG gọi LLM:

```python
class TemporalFacts(BaseModel):
    chart_id: str
    decadal: DecadalFacts          # 10-year palace, ages, mutagens
    yearly: HoroscopeLayer | None  # tứ hóa + palace map lưu niên (khi ?year)
    monthly: HoroscopeLayer | None # khi ?month
    daily: HoroscopeLayer | None   # khi ?day
    scopes_included: list[str]
```

Implementation: tái sử dụng `engine.get_horoscope(normalized, profile, anchor)` (đã tính đủ layers trong 1 call) — trả raw facts có cấu trúc, không format text. FE render trực tiếp.

## 5. API surface (thêm)

```
GET    /api/profiles                      → list (library)
POST   /api/profiles                      → {display_name, relationship?, chart_id} → profile
GET    /api/profiles/{id}                 → detail + chart_id
DELETE /api/profiles/{id}                 → xóa profile (chart giữ nguyên)
GET    /api/charts/{chart_id}/temporal?…  → TemporalFacts (§4)
GET    /api/charts/{chart_id}/readings    → InterpretationRun list (topic, target, status, created)
```

Compat: `POST /api/compatibility` giữ nguyên signature (chart ids); FE resolve `profile → chart_snapshot_id` trước khi gọi. Không đổi backend compat.

## 6. Frontend

- `/profiles` — grid card: display_name, ngày sinh tóm tắt, [Xem lá số]. "+ Thêm người" → birth form hiện có → sau create chart auto `POST /api/profiles`.
- `/compatibility` — thay input chart-id bằng 2 dropdown profile.
- `/charts/{id}/time` — navigator: đại hạn strip (từ natal data), year/month/day pickers → `GET temporal` render facts; nút topic → `POST /api/interpret` với `target={scope,…}` SSE stream.
- `/readings` + link từ chart: danh sách InterpretationRun (replay — `idempotency` đã có: GET lại run content, không regenerate).

## 7. Instrumentation (P1b)

Bảng `product_events` (server-side, append-only, không PII birth):

`chart_created, profile_created, interpret_started, interpret_completed, compat_started, temporal_opened(scope), reading_reopened`

Một endpoint `POST /api/events` (idempotent bằng client event id). Không third-party analytics.

## 8. Swe-2 worker = ReferenceModel

`eval/bench/devin_worker_shim.py` giữ vai trò **benchmark/judge** (p50 225–413s/turn — không phải consumer latency). Production `AI_BASE_URL` vẫn cần LLM nhanh qua OpenAI-compat; chọn model ở eval chứ không hard-code.

## 9. DoD v0.2

- [ ] Profile CRUD + library UI; compat chọn từ profile
- [ ] `GET temporal` deterministic, `TemporalFacts` schema test
- [ ] Navigator UI 4 tầng; nút topic → interpret SSE với TemporalTarget
- [ ] Reading library list + replay
- [ ] `product_events` table + emit 8 events
- [ ] Gate F: tests temporal endpoint (scopes compose đúng, target validation, profile→chart wiring)
- [ ] Tag `v0.2.0` sau merge hết

## 10. Out of scope v0.2 (explicit)

Auth/user accounts · K-line chart · share-link UX nâng cao · Today/Home daily digest · social features · KnowledgePack vi / RulePack / dataset mining / RAG · multi-language UI.
