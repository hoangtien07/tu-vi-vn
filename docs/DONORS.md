# DONORS — OSS repos tái sử dụng

Nguyên tắc: **reuse source code, not architecture debt**. Mọi code lấy về phải giữ license notice + attribution. Verify license lại trước mỗi lần port.

| Repo | License | Vai trò | Lấy gì | Không lấy |
|---|---|---|---|---|
| [Renhuai123/ziwei-doushu](https://github.com/Renhuai123/ziwei-doushu) | MIT (code); dataset license riêng | **UI + time donor** | `components/ChartBoard.tsx`, `PalaceCell`, `BirthForm`, `TimeNav`, `InsightPanel`, `ChatPanel`; `lib/ziwei/true-solar-time.ts` (reference), `patterns.ts` (1119 dòng pattern knowledge), `heming-knowledge.ts`, `lib/classics` (古籍, public domain), `wenmo-*` | `db-analysis.ts` (stub — proprietary đã rút), `dst-cn.ts` data TQ nguyên xi, architecture/backend assumptions |
| [x-haose/x-iztro](https://github.com/x-haose/x-iztro) | MIT | **Canonical engine** | `pip install x-iztro==0.6.1` — Rust core, Python binding, `to_text()`, `horoscope()`, `surrounded_palaces()`, `patterns_to_text()`, KnowledgePack schema v1 | Không vendored; pin version, qua `XiztroEngine` adapter duy nhất |
| [SylarLong/iztro](https://github.com/SylarLong/iztro) | MIT | **CI oracle** | JS `iztro@2.6.1` trong `scripts/differential/` để so x-iztro | Không phải runtime dep; không dùng hosted `iztro-ziwei-v3` |
| [por7/ziwei](https://github.com/por7/ziwei) (ZiweiKnows) | MIT | **UX donor (sau V1)** | match/hợp bàn UX, fortune K-line, share cards, OpenAI-compatible `llm.ts` patterns | Architecture của nó (Vite SPA, không layer tách) |
| [Crazycreate/Numerology](https://github.com/Crazycreate/Numerology) | MIT | **Prompt/provider donor** | `packages/ai` prompt patterns (topic prompts, anti-invent policies), Ollama provider pattern | Bát Tự logic, structured knowledge layer (chủ yếu cho Bát Tự) |
| [allanhung/starmoonhouse](https://github.com/allanhung/starmoonhouse) | check trước khi dùng | reference only | FastAPI+Ollama wiring example | Knowledge layer quá mỏng — không lấy làm base |

## Renhuai Dataset v3

- Release tag `v3.0-samples`, ~5.5GB, 518.400 = 60 × 12 × 30 × 12 × 2 (can chi × tháng × ngày × giờ × giới tính), mỗi mẫu: chart JSON + 13 chủ đề luận giải.
- Lưu ý coverage: state space natal thật ~561.600 = 60 × 12 × 30 × **13** × 2 dưới `day_divide=forward` (engine có 13 time indices — Tý sớm/Tý muộn khác chart trên cùng civil date). Dataset giả định 12 giờ/ngày → ~7% state space không có mẫu. Off critical path nhưng ghi nhớ khi mine dataset sau này.
- License: **free incl. commercial, attribution bắt buộc** (`DATASET-LICENSE` trong repo).
- **Không dùng trong runtime V1.** Vai trò sau: evaluation baseline, knowledge mining → x-iztro overlay pack, optional SFT (style/terminology VN). Tuyệt đối không `518k → embeddings → vector DB → production`.
- Lưu ý drift: dataset sinh bằng engine v3 tại thời điểm release — chart từ engine hiện tại có thể khác → chỉ dùng làm corpus, không phải oracle tuyệt đối.

## x-iztro notes đã verify (2026-09-23)

- PyPI `x-iztro 0.6.1`, MIT, Python ≥3.10, abi3 wheels (Linux/macOS/Windows — không cần Rust toolchain), zero runtime deps, typed API (dataclasses + StrEnum), typed errors không panic.
- Parity field-for-field với iztro v2.6.1 qua 716.314 golden cases; 6 tầng vận hạn; 64 pattern rules; reverse lookup.
- `Astro().by_solar("2000-8-16", 2, "female", language="en-US")`; `chart.to_text()` ~3.3k chars facts → ~20k với knowledge.
- Built-in KnowledgePack **hiện chỉ zh-CN** → spec §7 language strategy (chart `vi-VN` + pack `zh-CN` explicit — verified combo chạy: labels vi + prose zh).
- i18n `vi-VN` hoàn chỉnh cho chart labels (Mệnh, Liêm Trinh, Thổ Ngũ Cục...); language không ảnh hưởng computation.
- `horoscope(target_date)` nhận solar date đầy đủ, trả đủ 6 scopes/1 call, không validate pre-birth. `monthly_list` trả 14 items năm nhuận. `yearly_list()` bắt buộc decadal ordinal hoặc palaceKey (docs nói optional — sai).
- Footgun verified: `chart.to_dict()['config']` drop custom `mutagens`/`brightness` → ChartConfig luôn rebuild từ `engine_profiles`.
- Differential thật vs iztro@2.6.1 (8 natal cases gồm 太阳酉=平/七杀酉=旺, ageDivide=birthday, dayDivide 2 modes): 0 divergence — council đã chạy trực tiếp.
- Pre-1.0 + cộng đồng nhỏ → pin version + differential oracle (SPEC §20).
