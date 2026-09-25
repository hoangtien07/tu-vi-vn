# SPEC v0.5 — Dataset mining → VN KnowledgePack

Roadmap: "v0.5.0 Dataset mining / fine-tuning / RAG chỉ nếu eval chứng minh
cần". User chọn nhánh **dataset mining → RulePack/Pack**; RAG và fine-tune
vẫn cấm. Không đụng engine, không đổi runtime code.

## Bài toán

`builtin` pack là zh-CN lore. `vn-seed-v1` (58 entries viết tay) hòa với
ablation `none` ở subset tournament — chưa có bằng chứng VN lore thắng.
v0.5 mine **Renhuai Dataset v3** thành pack VN có lượng — rồi chứng minh
bằng tournament (I18 gate siết: thắng `builtin` **và** `none`, judge on).

## Dataset (đã xác minh nguồn)

- Release `v3.0-samples` trên `Renhuai123/ziwei-doushu`: 518.400 mẫu =
  60 năm can chi × 12 tháng âm × 30 ngày âm × 12 giờ × 2 giới tính;
  ~5.5GB trong 3 part zip (`ziwei-samples-v3-part{1,2,3}.zip.00{1,2,3}`
  + `SHA256SUMS.txt`); join = `cat part*.zip.00* > full.zip`.
- Mỗi mẫu: chart JSON + **13 chủ đề luận giải** (命格总览、财运、事业、
  感情、健康… — text **zh-CN**, hệ Nghê Hải Hạ《Thiên Kỷ》).
- License: free use, commercial ok, **bắt buộc attribution** — cite nguồn
  trong pack metadata + THIRD_PARTY_NOTICES.
- Known gaps (ghi trong DONORS.md): thiếu ~7% state space (dataset giả định
  12 giờ/ngày, engine có 13 time indices — Tý sớm/Tý muộn); chart sinh bởi
  engine v3 → **drift so với x-iztro hiện tại** → corpus ≠ oracle.

## Ranh giới (invariants mới)

- **I20 — corpus offline-only.** Dataset sống ở `eval/dataset/` (gitignored,
  ~5.5GB) + `eval/mining/fetch_dataset.sh` (download 3 parts, verify
  SHA256SUMS, join). Không commit raw data; không runtime code nào đọc nó.
- **I21 — mine rules, không canned text.** Per-chart text copy nguyên vào
  pack = generic + đúng điểm yếu council reject. Output = rule entries
  tổng hợp **across charts**: (entity signature → theme lặp lại trên ≥N
  mẫu). Mỗi entry ghi `meta: {sampleCount, topics, source}` để audit.
- **I22 — drift filter.** Trước khi mine text của một mẫu, re-cast chart
  bằng engine hiện tại; mẫu có canonical signature khác dataset JSON → bỏ
  (ghi driftRate vào report). Không mine text của chart engine không tái
  hiện được.
- **I23 — VN-ize curated, không raw zh.** Pack entries cuối là tiếng Việt.
  Mined candidates giữ `sourceText` zh + `intro` VN (dịch+đúc kết). LLM
  được phép trong **offline pipeline** (dịch/đúc kết lore — không phải
  tính lá số), và là chi phí eval chứ không phải runtime.
- **I24 — gate siết.** Khác v0.4 (tie được chấp nhận): vn-mined chỉ thắng
  nếu trên frozen corpus (24 charts × 5 topics, fresh runs): 0 grounding
  fail **và** judged rubric > `builtin` **và** > `none` (strict greater —
  tie lại = giữ builtin). Subset + coverage được phép ghi rõ nếu budget
  hạn chế, nhưng verdict "winner" cần full corpus.

## Pipeline (eval/mining/, không vào runtime)

```
D0 fetch_dataset.sh     → eval/dataset/ (3 parts → join → sha256 → unzip)
D1 mine.py              → candidates.jsonl
     per sample: parse chart JSON → entity signature
       (palace × majorStars × mutagens × pattern hits)
     re-cast bằng engine hiện tại → signature match? (I22)
     group by (entityKey, topic) → collect texts → recurring phrases
       (sentence-level frequency ≥ N=3) → candidate rule
D2 pack.py              → eval/packs/vn-mined-v{N}.json
     top-K candidates/entity → VN intro (LLM-assisted dịch+đúc kết hoặc
     curated thủ công cho subset đầu) → schema giống vn-seed-v1 +
     meta{sampleCount,source,sourceText}
D3 tournament           → eval/tournament/reports/
     KNOWLEDGE_PACK=eval/packs/vn-mined-v{N}.json vs builtin vs none
D4 decision             → report md + IMPLEMENTATION_PLAN log
     winner → optional: default KNOWLEDGE_PACK; tie/lose → giữ builtin,
     pack ở eval-only
```

### Entity signature

Định danh entity để group mẫu — tái dùng key space KnowledgePack đã có:
`star:{key}` (14 chính tinh), `pattern:{key}`, `palace:{nameKey}×star:{key}`
(vị trí sao), `mutagen:{kind}×star:{key}` (sa hóa nào). Signature chart =
tập tất cả entity keys nó chạm → mẫu "vote" vào mọi group của nó.

### N + K

- N=3 mẫu trùng phrase → candidate (giảm noise nhưng không bỏ pattern hiếm).
- K=5 candidates/entity/topic (đủ cho excerpt 1-3 câu/pack entry).
- Entity không có candidate → entry vắng → fallback lore builtin
  (KnowledgeRegistry đã per-entity — pack chỉ override phần nó định nghĩa).

## DoD

- [ ] `eval/mining/` pipeline: fetch_dataset.sh (sha256 verify), mine.py,
  pack.py — chạy được từ dataset gốc, deterministic (không LLM trong D1).
- [ ] `eval/packs/vn-mined-v1.json` — schema khớp vn-seed-v1 + meta fields;
  coverage report (entities covered/total, driftRate).
- [ ] Tournament subset ≥4 charts × 5 topics × 3 variants, judge on nếu
  budget cho phép; report ghi coverage rõ ràng.
- [ ] Decision documented trong IMPLEMENTATION_PLAN v0.5 log — pack chỉ
  thành default nếu pass I24 gate.
- [ ] THIRD_PARTY_NOTICES cập nhật attribution dataset.
- [ ] Không runtime code change ngoài (nếu cần) `settings` default —
  app vẫn `KNOWLEDGE_PACK=builtin` cho tới khi gate pass.
