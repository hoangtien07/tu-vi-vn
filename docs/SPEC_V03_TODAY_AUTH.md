# SPEC v0.3 — Today / Daily + Auth + Chat Context

Kế thừa `SPEC.md` (invariants I1–I8) và `SPEC_V02_PROFILES_TIMELINE.md` (I9–I12).
Milestone: chuyển v0.2 (Profiles + Time Navigator) thành sản phẩm có lý do
quay lại hằng ngày, với ownership thật — vẫn **100% self-hosted**.

## Scope

```
P0  Today card       — deterministic daily facts on open, LLM on demand
P0  Auth nhỏ         — email+password, session cookie, profile ownership
P1  Chat context     — chat nhận TemporalTarget; entry từ navigator/today
```

Non-goals (cùng phòng v0.2): K-line visualization, RAG/dataset/fine-tune,
social/sharing-discovery, Google OAuth (xem §3), thay đổi engine,
swe-2 làm production inference (ReferenceModel giữ nguyên).

## I. Invariants mới

- **I13 — Today mở ra là deterministic.** `GET /api/charts/{id}/today` chỉ
  trả engine facts + highlight candidates trích theo rule. Không LLM call
  khi render. Narrative chỉ sinh khi user bấm hoặc cache miss — giống
  Time Navigator (I9).
- **I14 — Auth không phá self-host.** Password auth hoàn toàn nội bộ
  (argon2 hash, session table, HttpOnly cookie). Google OAuth **loại khỏi
  v0.3** vì verify token cần gọi Google endpoint — vi phạm I3 (no runtime
  external requests ngoài `AI_BASE_URL`). Cân nhắc lại khi chính sách I3
  được nới có chủ đích cho IdP.
- **I15 — Ownership append-only.** Profile/chart hiện có (anonymous,
  `owner_key="local"`) vẫn hoạt động nguyên vẹn; login không chiếm hay
  ẩn dữ liệu local. `visibility` mặc định `private`.
- **I16 — Chat dùng chung contract.** `ChatRequest` nhận optional
  `target: TemporalTarget` — đúng một contract temporal, không pipeline
  riêng (I10 mở rộng sang chat).

## II. P0 — Today / Daily

### API

```
GET /api/charts/{id}/today[?date=YYYY-MM-DD]
→ 200 {
    chartId, date,
    facts: { decadal, yearly, monthly, daily, age }   // temporal layers, như /temporal
    highlights: [{ palace, topicHint, summary }]      // ≤3, rule-extracted
  }
```

- `date` mặc định = hôm nay (server timezone); `?date` cho debug/replay.
- Facts: tái dùng `engine.get_horoscope` pipeline của `/temporal` — cùng
  anchor `dt.date(y,m,d)`, cùng layer set. Không code mới cho engine.
- `highlights`: rule-based extraction từ daily layer — cung lưu nhật,
  tứ hóa lưu nhật, sao chính của cung — map sang topicHint
  (career/wealth/love/health/overview) bằng mapping cố định
  `PALACE_TOPIC_HINT` trong code (Mệnh→overview, Quan Lộc→career,
  Tài Bạch→wealth, Phu Thê→love, Tật Ách→health). Không LLM, không
  heuristic-free text.

```
POST /api/charts/{id}/today/brief { date? }
→ SSE stream giống interpret (metadata → evidence → delta → replace → done)
```

- Persist như `InterpretationRun` với `topic="today"`,
  `target={scope:"daily", year, month, day}` — replay bằng Reading
  Library sẵn có, không UI riêng.
- Idempotent theo (chart, date): cùng ngày + cùng versions → replay run cũ
  (idempotency layer hiện có).

### UI

Trên `/chart/[id]` + link từ `/profiles` card:

```
Hôm nay — 24/09/2026
──────────────────────
• Công việc — <summary>
• Tài chính — <summary>
• Quan hệ  — <summary>
[Căn cứ]            [Luận chi tiết hôm nay]   [Hỏi thêm]
```

- `[Căn cứ]` toggle mở raw facts (evidence-style panel, tái dùng
  FactBlock của TimeNavigator).
- `[Luận chi tiết]` → POST today/brief → SSE vào panel (reuse
  InterpretPanel SSE handling).
- `[Hỏi thêm]` → mở chat panel với `target = daily today` (§IV).

## III. P0 — Auth nhỏ

### Data model (migration 0004)

```python
class User(Base):
    id          # "u_" + uuid4().hex[:16]
    email       # unique, citext-lowered
    password_hash  # argon2id
    created_at

class AuthSession(Base):
    id          # token hash (sha256), không lưu raw
    user_id     # FK users
    expires_at  # 30 ngày rolling
    created_at

# profiles: + user_id nullable (FK users) — anonymous giữ owner_key="local"
```

### Endpoints

```
POST /api/auth/register { email, password }   → 201 + Set-Cookie
POST /api/auth/login    { email, password }   → 200 + Set-Cookie
POST /api/auth/logout                          → 204, xóa cookie
GET  /api/auth/me                              → { id, email } | 401
```

- Cookie `tv_session`: HttpOnly, SameSite=Lax, Secure khi prod
  (`settings.env != "dev"`), path=/api.
- Password policy tối thiểu: ≥8 ký tự. Rate-limit login: 10/5 phút/IP
  (in-process bucket, đủ cho self-hosted V1).
- `get_current_user(session)` dependency: đọc cookie → hash → lookup →
  401. Optional variant `get_optional_user` trả None khi anonymous.

### Ownership wiring

- `POST /api/profiles`: logged-in → `user_id=me`; anonymous →
  `owner_key="local"` (giữ nguyên hành vi cũ).
- `GET /api/profiles`: logged-in → `user_id=me OR owner_key="local"`;
  anonymous → `owner_key="local"`. Merge view, không import/migrate.
- Chart share link (`/s/{token}`, `/chart/{id}`) **không đổi** —
  capability URL vẫn là cơ chế xem chéo; auth chỉ quản Profile.
- `PATCH/DELETE /api/profiles/{id}`: chỉ owner (user_id khớp, hoặc
  anonymous khi owner_key=local — giữ semantics cũ cho local).

### UI tối thiểu

- `/login`, `/register` — form đơn giản; header hiện email hoặc
  "Đăng nhập".
- Không onboarding flow, không profile settings page.

## IV. P1 — Chat context

- `ChatRequest` thêm `target: TemporalTarget | None` (optional).
- `ChatService.respond` khi có target → compose context với temporal
  scopes của target (tái dùng `temporal_scopes_for` — hệ quả của I10
  là một chỗ duy nhất quyết định).
- Entry points mới: nút "Hỏi thêm" trên Today card và Time Navigator →
  chat panel mount với `target` hiện tại (daily/yearly/…). Conversation
  vẫn chart-scoped (không đổi model).
- Grounding: temporal claims trong chat cite `horoscope_fact` cùng rule
  với interpret (I4) — validator đã cover nếu context có facts.

## V. Product events bổ sung

| event              | khi nào                                     |
|--------------------|---------------------------------------------|
| `today_opened`     | Today card mount /chart (facts fetch)       |
| `today_brief`      | bấm Luận chi tiết hôm nay                   |
| `auth_registered`  | register thành công                         |
| `auth_login`       | login thành công                            |
| `chat_sent`        | gửi message (meta: hasTarget)               |

Dedupe `clientEventId` + cap meta 4KB giữ nguyên (0003).

## VI. Out of scope (ghi rõ)

- Google/OAuth providers — cần external IdP call, chờ quyết định nới I3.
- "Share link" cho profile/reading — visibility field đã có, enforcement
  UI deferred.
- Email verification / reset password — deferred; self-hosted V1 không
  có SMTP. Ghi rõ trong README: password không reset được.
- Home dashboard gom nhiều profile — Today là per-chart; aggregate
  "hôm nay của cả nhà" để sau metrics nói có nhu cầu.
- K-line, lịch âm-dương picker nâng cao, notification.

## VII. DoD

- [ ] `GET /api/charts/{id}/today` deterministic, không LLM (test đếm
      provider calls = 0).
- [ ] Highlights ≤3, topicHint trong enum, tất cả trace tới daily facts.
- [ ] `POST /today/brief` SSE hoàn chỉnh + idempotent replay cùng ngày.
- [ ] Register/login/logout/me + cookie flags đúng; login rate-limit.
- [ ] Anonymous profiles hiện có không mất sau migration 0004; logged-in
      thấy local + owned.
- [ ] Chat nhận `target` → context gồm đúng scopes (unit test).
- [ ] 5 event mới emit; migrations batch-mode sqlite-safe.
- [ ] Tests: auth flow, ownership isolation, today determinism,
      chat-with-target ≥ 12 case; suite cũ xanh.
- [ ] Tag `v0.3.0` sau khi merge hết.
