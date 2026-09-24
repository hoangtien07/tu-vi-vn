# SPEC — Compatibility / Hợp bàn (V2 feature, trên foundation V1)

Trạng thái: draft spec — chưa code. Kế thừa nguyên tắc Auditable Ziwei
Reasoning System: deterministic engine trước, evidence có id, LLM chỉ diễn
đạt — **LLM ≠ Ziwei calculator, cũng ≠ compatibility scorer**.

## 1. Phạm vi

Hợp bàn = soi tương tác giữa **hai lá số đã tồn tại** (immutable
`ChartSnapshot`). KHÔNG phải: composite chart mới, match score số hóa,
hay RAG.

Input: `chart_a_id`, `chart_b_id` (hai snapshot đã cast), optional
`target` (dùng lại `InterpretTarget` V1.1 — V1 hợp bàn mặc định
`target=None`, chỉ natal).

## 2. Phép hợp bàn truyền thống → evidence deterministic

Bốn nhóm phân tích kinh điển, tất cả suy ra được từ `CanonicalChartDTO`
của hai lá — không cần engine mới:

| Nhóm | Nội dung | Evidence kind |
|---|---|---|
| Mệnh–Mệnh | A.soulPalace vs B.soulPalace: sao chính, can-chi, độ sáng | `palace_fact` (scope `natal:a`/`natal:b`) |
| Mệnh ↔ Phu Thê | A.Mệnh khớp với B.Phu Thê (và ngược lại): sao B.Phu Thê có xuất hiện/chiếu trong A.Mệnh–tam hợp | `palace_fact` + `cross_link` |
| Tứ hóa chéo | Can năm sinh A sinh {祿權科忌} → sao đó nằm ở cung nào của B; ngược lại B→A | `cross_link` (NEW kind) |
| Chi/Zodiac | Mệnh chi A vs Mệnh chi B: đồng chi / tam hợp / lục hợp / xung | `cross_link` |

### 2.1 `cross_link` item (deterministic)

```text
A's mutagens: for m in A.birth_stem_tứ_hóa {starKey, mutagen ∈ 祿權科忌}
    palace_b = B.palace_containing(starKey)   # search B's major+minor stars
    item: kind=cross_link, scope=cross:a→b,
          entity_key=f"a:{m.starKey}→b:{palace_b.nameKey}",
          data={from_side:"a", star, starKey, mutagen,
                lands_in:{palaceKey, palaceName, branch}}
```

- Mỗi bên ≤4 items (4 tứ hóa) → cross tổng ≤8 + 1 item chi-relation
  (`a.soulBranch vs b.soulBranch`, relation computed = đồng/tam-hợp/
  lục-hợp/xung/lục-hại — bảng tra deterministic).
- Star không tìm thấy trong B (edge: sao chỉ có ở palace ngoài bảng)
  → item vẫn emit với `lands_in=null` + note "không đóng vào cung nào
  của B" — evidence vẫn audit được.

### 2.2 Palace-pair items

`ComparisonComposer.compose_pair(dto_a, dto_b)`:

```text
items  = chart_fact(a) + chart_fact(b)                  # soul/body/cục
       + palace_fact(a.soulPalace + 三方四正)
       + palace_fact(b.soulPalace + 三方四正)
       + palace_fact(a.spousePalace + 三方四正)
       + palace_fact(b.spousePalace + 三方四正)
       + mutagen(a, all palaces) + mutagen(b, all)      # như V1.1
       + cross_link(A→B) + cross_link(B→A)
       + knowledge excerpts (compatibility pack)
```

`scope` field mang side-tag: `natal:a`, `natal:b`, `cross:a→b`,
`cross:b→a`. Topic fixed: `"compatibility"` (không phải 12 topics thường).

## 3. Persistence & API

### 3.1 Run model

Mở rộng `InterpretationRun` thay vì bảng mới — một audit trail duy nhất:

- migration: `+ partner_chart_id uuid NULL`
- `chart_id` = chart_a (request order); `topic` CHECK/`Literal` thêm
  `"compatibility"` (chỉ endpoint hợp bàn gán được).
- `version_meta` thêm `chartB`, `sides:{a:chart_id, b:partner_chart_id}`.

Idempotency key — pair được **canonicalize** (`min(chart_a,chart_b)`,
`max(...)`) trước `|`-join: bundle đối xứng nên (A,B) và (B,A) hit cùng
run; thứ tự trình bày lưu trong `version_meta.sides`.

### 3.2 Endpoint

`POST /api/compatibility` — body:

```json
{
  "chart_a_id": "cs_...", "chart_b_id": "cs_...",
  "target": null | {scope, year, month?, day?},
  "namespace": null | str
}
```

- `chart_a_id == chart_b_id` → 422 (`self_pair`).
- SSE giữ nguyên contract V1: `metadata → evidence(bundle pair) →
  delta* → (repair → replace)? → done`, `replay` nếu idempotency hit.
- `GET /api/compatibility/{run_id}` đọc lại run (reuse interpret run
  read path nếu có).

## 4. LLM surface

- `prompts/topics/compatibility.md` mới — template yêu cầu đối chiếu
  hai phía qua `[E###]`, cấm so điểm số, cấm đương đầu dự đoán vận hạn
  nếu `target=None`.
- `template_sha256("compatibility")` + `prompt_version` chạy đúng cơ chế
  có sẵn (topic là key của chúng).
- GroundingValidator giữ nguyên: closed-world vocab = hợp của 2 chart
  (`_walk` trên cả items a/b/cross), invented-entity, ref-existence,
  temporal↔horoscope (chỉ khi có target).

## 5. Eval & gates

- **Gate A**: 422 cho `chart_a==chart_b`, chart không tồn tại, target
  sai contract (reuse `InterpretTarget` model).
- **Gate B**: same pair → same `context_hash`/bundle ids; cross_link
  tứ hóa đúng cung đích trên ≥3 chart fixtures tính tay.
- **Gate C**: cases `compatibility.json` — invented entity từ chart thứ
  ba, ref hỗn hợp, claim temporal thiếu horoscope (khi target set).
- **Gate D**: chat KHÔNG route tới compatibility (topic ngoài
  `V1_TOPICS`) — giữ nguyên routing.
- **Gate E3** (khi có LLM budget): 6–10 cặp chart × compatibility,
  fresh namespace — report như E1/E2.

## 6. Phases

| Phase | Nội dung | Deliverable |
|---|---|---|
| C0 | Spec này | doc này |
| C1 | cross engine (`cross_link` items) + `ComparisonComposer` + builder kind + migration `partner_chart_id` + `POST /api/compatibility` SSE + prompt topic | backend đầy đủ |
| C2 | eval cases A/B/C compat + tests | CI xanh |
| C3 | Web UI: chọn/nhập 2 lá số → xu hợp bàn, xem evidence | trang /compatibility |
| C4 | Bench E3 khi có AI budget | report |

DoD C1–C2: endpoint chạy SSE đúng contract, cross_link audit được tới
từng cung đích, không runtime request tới dịch vụ ngoài ngoài AI_BASE_URL.

## 7. Không làm (V2)

- Composite/synastry chart mới, điểm số tổng hợp, soi >2 lá số, match
  nhiều profile (auth), đại hạn sync đôi (phase sau khi timeline feature
  tới), RAG/dataset mining.
