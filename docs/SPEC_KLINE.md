# SPEC — Vận trình K-line (temporal visualization)

Deferred từ v0.2; chọn làm sau v0.4 tournament. Mục tiêu: trực quan hóa
temporal data engine đã tính sẵn (đại hạn → lưu niên) thành dải "K-line"
vận trình trên trang Time Navigator.

## Nguyên tắc

- **Chỉ hiển thị facts deterministic.** Không tổng hợp "điểm vận" scalar
  (ví dụ 7.2/10) — tử vi không có metric chuẩn như vậy; bịa score vi phạm
  honesty contract của hệ thống. Glyph encode trực tiếp facts: tứ hóa,
  cung lưu mệnh, can chi.
- **Không gọi LLM khi render.** Strip load một call deterministic; AI vẫn
  on-demand qua luồng "Luận bằng AI" hiện có.
- **Không đụng engine** — chỉ đọc `get_horoscope` per-year anchors.

## Data contract

`GET /api/charts/{chart_id}/temporal/decade?year=YYYY`

Engine `get_horoscope` được gọi cho các năm quanh `year` để tìm đúng đại hạn
đang chứa nó (boundary = nơi `decadal.index` đổi). Không suy năm từ tuổi mụ
(tránh off-by-one âm lịch đầu năm).

```json
{
  "chartId": "...",
  "decadal": {
    "index": 1, "name": "Đại Hạn",
    "mutagen": ["Vũ Khúc","Tham Lang","Thiên Lương","Văn Khúc"],
    "mutagenStarKeys": [...], "heavenlyStem": "Kỷ", "earthlyBranch": "Mão",
    "palaceName": "Phụ Mẫu", "palaceNameKey": "parentsPalace",
    "ageRange": [36, 45]
  },
  "years": [
    {
      "year": 2025,
      "heavenlyStem": "Ất", "earthlyBranch": "Tỵ",
      "yearlyIndex": 4, "palaceName": "Tử Nữ", "palaceNameKey": "childrenPalace",
      "mutagen": ["Cơ Hóa Lộc...", ...], "mutagenStarKeys": [...]
    }
  ],
  "yearRange": [2024, 2033]
}
```

- `mutagen`/`mutagenStarKeys` order = `[Lộc, Quyền, Khoa, Kỵ]` — confirmed
  trong source x_iztro (`mutagen_star_keys` docstring: 禄、权、科、忌).
- `ageRange` lấy từ `palaces[decadal.index].decadal.range` của natal chart
  (đã có trong ChartSnapshot DTO — không cần call thêm).
- `stars` (lưu tinh per-palace) cố ý KHÔNG trả trong decade endpoint —
  giữ payload compact; chi tiết sao xem qua `/temporal` hiện có khi user
  click một năm.

## UI — `KlineStrip` trên Time Navigator

Row ~10 glyph, mỗi glyph = một lưu niên:

```
 ĐẠI HẠN  Kỷ Mão · Phụ Mẫu (36–45 tuổi)
 tứ hóa: Vũ Khúc(L) Tham Lang(Q) Thiên Lương(K) Văn Khúc(Kỵ)
─────────────────────────────────────────────────────────
 ẤtTỵ  BínhNgọ  ĐinhMùi  MậuThân  KỷDậu ...
 2025   2026    2027    [2028]   2029
 ┌──┐   ┌──┐    ┌──┐     ┌──┐     ┌──┐
 │LQ│   │··│    │··│     │LK│     │··│
 │KK│   │··│    │··│     │QK│     │··│
 └──┘   └──┘    └──┘     └──┘     └──┘
 Tử Nữ  Phu Thê Huynh Đệ  Mệnh    Phụ Mẫu
```

- 4 mutagen chip xếp dọc theo order L-Q-K-Kỵ, màu theo hóa:
  Lộc = emerald, Quyền = amber, Khoa = sky, Kỵ = rose (tooltip tên sao đầy đủ).
- Dưới glyph: cung lưu mệnh (`palaceName`).
- Năm đang chọn highlight; năm hiện tại đánh dấu chấm.
- Click glyph → set `year` của navigator → facts + AI on-demand (tái dùng
  luồng hiện có, event `temporal_opened` không đổi).
- Đại hạn header hiển thị tứ hóa của chính đại hạn.
- Prev/next decade: giảm/tăng `year` ±10 → decade mới (engine tự resolve
  đại hạn đúng).

## DoD

- [x] Endpoint `/temporal/decade` + tests (boundary năm đổi đại hạn, năm
  trước sinh → 422, compact payload không chứa `stars`).
- [x] `KlineStrip` render đúng 10 glyph, màu tứ hóa, click → đổi năm
  navigator.
- [x] Không LLM call khi render strip; không scalar "điểm vận" nào.
- [x] Tests + ruff + mypy + tsc + build xanh; PR + automerge.
