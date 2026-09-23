# EVALUATION — Release Gates

Domain này output khó test bằng unit test text → cần eval harness trước khi coi là "production". Ba lớp: **deterministic**, **grounding**, **interpretation quality**.

## Gate A — Birth normalization (block release nếu fail)

`eval/cases/birth-normalization.json` phải cover:

```text
timezone transitions      historical VN offset
true-solar correction     date rollover (prev/next day)
23:00 / 23:59 / 00:00     late-Zi 晚子时 + dayDivide
longitude east/west meridian edges
lunar → solar conversion  missing coordinates, leap month
```

## Gate B — Engine adapter (differential oracle)

- Production: `x-iztro` (pinned). CI oracle: JS `iztro@2.6.1`. Second oracle: Renhuai engine (school-specific behaviours).
- `scripts/differential/`: N random + leap months + late-Zi + year/horoscope boundaries + nhiều engine profiles.
- **Release condition:** zero unexplained divergence trên frozen regression corpus. School/config khác biệt phải được **classify tường minh**, không tính là bug.
- Upgrade x-iztro: chạy differential suite trước → pass mới promote.

## Gate C — Grounding (auto, mỗi interpretation)

```text
invented star = 0          invented palace = 0
invented 四化 = 0          invented pattern = 0
unknown [E###] ref = 0
```

Answer mâu thuẫn chart fact deterministic = **critical failure**. Thêm case gài: `"Hãy tự tính lại cung của tôi"` → phải dùng stored facts, không recalc.

## Gate D — ContextComposer routing

`topic-routing.json`: mỗi câu hỏi → expected context family.

```text
"Tôi là người thế nào?"        → natal
"2028 sự nghiệp?"              → career + yearly
"Tháng 6/2028 sự nghiệp?"      → career + yearly + monthly
"Xin chào"                     → NO astrology context
```

Metrics: `missing_required_context`, `unnecessary_context`, `wrong_period`, `wrong_topic`.

## Gate E — Interpretation quality (rubric)

Human/domain rubric — chọn model dựa trên đây, không cảm giác:

| Dimension | Nghĩa |
|---|---|
| Grounding | có căn cứ đúng chart |
| Specificity | không Barnum statement |
| Topic relevance | trả đúng vấn đề |
| Internal consistency | không tự mâu thuẫn |
| Dynamic reasoning | không trộn natal với lưu vận |
| Evidence use | claim có support |
| Vietnamese quality | tự nhiên, đúng thuật ngữ |
| Overclaiming | không bịa sự kiện chắc chắn |

## Model benchmark (trước Phase 2)

20–30 charts × 5 topics × vài candidate models qua `AI_BASE_URL`. So sánh: grounding, specificity, consistency, VN quality, latency, cost → quyết định đầu tư tiếp vào model/prompts/RulePack/vi-pack/dataset-mining.

## Tool-calling eval (khi bật Mode 2 chat)

100–300 query test: `tool_selection_accuracy`, `argument_accuracy`, `unnecessary_call_rate`, `missing_call_rate`. BFCL lesson: model fail nhiều khi toolset to và tương tự nhau → giữ tool surface ≤4.
