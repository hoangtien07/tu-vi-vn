# SPEC v0.4 — Knowledge Quality Tournament

Mục tiêu: quyết định **bằng bằng chứng** xem knowledge lore có giúp interpretation tốt hơn không, và một VN RulePack (tiếng Việt, curated) có đánh bại zh-CN builtin không — trước khi đầu tư viết full pack. Roadmap đã chốt: "v0.4.0 Knowledge quality tournament / RulePack nếu cần". Không RAG, không dataset mining, không fine-tune, không đụng engine.

## Invariants mới

- **I17 — Pack selection explicit & pinned.** Knowledge pack được chọn qua cấu hình rõ ràng (`KNOWLEDGE_PACK` env hoặc eval override), id+version ghi vào `InterpretationRun.metadata.knowledgePacks` (đã có sẵn). Không có pack "lặng lẽ" đổi theo thời gian.
- **I18 — Tournament quyết bằng số, không quyết bằng cảm giác.** Winner chỉ được công nhận khi: grounding failures = 0 trên frozen corpus **và** judge rubric trung bình ≥ baseline (sai số report kèm). Mọi kết quả commit vào `eval/tournament/reports/`.
- **I19 — Knowledge là lore, không phải chart fact.** Pack mới chứa mô tả sao/cung/cách cục/tứ hóa; cấm chứa dữ liệu lá số, tên người, hoặc bảng tra tính toán (đã có engine).

## Background kỹ thuật (đã verify trên code)

- `ContextComposer._knowledge_items` gọi provider duck-typed: `star_excerpt`/`pattern_excerpt`/`palace_excerpt` (+ `version_info` cho pin). Hiện `KnowledgeRegistry` hard-code `KnowledgePack.builtin("zh-CN")`.
- x_iztro chỉ có builtin zh-CN (verify: `builtin('vi-VN')` / `('en-US')` → error). `KnowledgePack.from_dict` load pack từ dict schema `{id, language, version, source, schema, concepts, extends, stars{}, palaces{}, patterns{}, mutagens{}}`.
- `run` đã pin `knowledgePacks: [version_info()]` — mọi run của variant nào cũng tự ghi nguồn lore.
- Frozen corpus sẵn có: `eval/bench/charts.json` (24 charts) + `run_bench.py` (suites static/yearly/compat + judge rubric + grounding report).

## Variants (vòng đầu)

| ID | Pack | Mục đích |
|----|------|----------|
| R0 | `none` — ablation | Lore có giúp không hay chỉ thêm noise? |
| R1 | `zh-CN` builtin (baseline, hiện tại) | Baseline |
| R2 | `vn-seed-v1` — VN RulePack curated | VN lore có thắng zh-CN không |

## Components

### 1. Configurable knowledge provider (`apps/api`)

- `KnowledgeRegistry` đọc env `KNOWLEDGE_PACK`:
  - unset / `builtin` → zh-CN builtin (hiện tại, giữ default).
  - `none` → `NullKnowledge`: mọi `*_excerpt` trả `None` (composer skip knowledge items); `version_info` → `{"id": "none", "version": "0"}`.
  - `/abs/path/*.json` → `KnowledgePack.from_dict(json.load(f))`; `version_info` từ pack.
- Duck-type giữ nguyên — composer không đổi.
- `GET /api/health` (hoặc `/version` nếu có) trả thêm `knowledgePack.id` để tournament runner verify API đang chạy đúng variant.

### 2. Pack format + `eval/packs/`

- Pack file = JSON `from_dict` schema (cùng `to_dict()` của builtin).
- `eval/packs/README.md`: schema fields bắt buộc (`id,version,language,source{url,commit,license}` + ít nhất 1 trong `stars/palaces/patterns/mutagens`), quy tắc attribution (lore adapt từ zh-CN MIT pack ghi nguồn).
- `eval/packs/vn-seed-v1.json`: entries tiếng Việt cho các star/palace/pattern/mutagen keys **thực sự được cite** trong bench outputs hiện có (mine `eval/bench/reports/` cho cited entity keys; ~40–80 entries). Mỗi entry: `name` VN + `excerpt` ≤300 ký tự tóm tắt lore truyền thống (diễn giải từ zh-CN, ghi `source` zh-CN pack + "adapted").

### 3. Tournament runner (`eval/tournament/run_tournament.py`)

```
python -m eval.tournament.run_tournament \
  --variants none,builtin,eval/packs/vn-seed-v1.json \
  --suite static [--charts-n 24] [--judge] \
  --api-url http://localhost:8000 --llm-endpoint <worker-shim|provider>
```

- Mỗi variant: spawn `uvicorn app.main:app` subprocess với `KNOWLEDGE_PACK=<variant>` trên port tạm (hoặc reuse API đang chạy nếu `--reuse-api` + verify `/health.knowledgePack`), chạy suite qua `run_bench` logic (import, không copy-paste), thu: grounding failures, per-dimension rubric, latency.
- Report `eval/tournament/reports/<ts>.md`: bảng per-variant (runs, done, grounding fails, rubric means, p50 latency) + verdict theo I18 + `winner` field.

### 4. Decision gate

- R2 thắng R1 theo I18 → lên kế hoạch mở rộng vn-seed thành pack đầy đủ (v0.4.x follow-up); R1 thắng/hòa → giữ zh-CN, bỏ ý định VN pack; R0 thắng cả hai → knowledge excerpts là noise → cân nhắc rút lore khỏi composer (decision ghi trong report, không tự đổi code).
- Không auto-switch production pack. `KNOWLEDGE_PACK` env đổi = deploy config change, qua PR.

## Out of scope

- Dataset 518k mining, RAG/vector store, embeddings, fine-tune.
- Pack cho compatibility (cross_link knowledge) — v0.4.x nếu R2 thắng.
- Realtime pack switching / per-request pack param (attack surface; eval subprocess env đủ).
- New x-iztro features.

## Testing

- Unit: `KNOWLEDGE_PACK=none` → compose trả bundle không có `kind="knowledge"` item; pack file tốt → `star_excerpt` trả entry VN; file xấu/missing → startup error rõ.
- Tournament smoke: `--charts-n 2` chạy được end-to-end với `llm_provider=None` (assert chỉ plumbing — grounding/judge rỗng).
- Mypy+ruff sạch.

## DoD

- [ ] `KNOWLEDGE_PACK` env (builtin|none|path) + `NullKnowledge` + health expose pack id
- [ ] `eval/packs/` + schema README + `vn-seed-v1.json` (entries từ cited keys thật)
- [ ] `eval/tournament/run_tournament.py` + report đầu tiên (≤ subset nếu inference budget giới hạn — ghi rõ coverage)
- [ ] Quyết định pack ghi vào report + IMPLEMENTATION_PLAN tick
- [ ] Tag `v0.4.0` sau khi merge
