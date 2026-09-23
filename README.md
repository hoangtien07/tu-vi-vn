# tu-vi-vn

**Auditable Ziwei Reasoning System** — nền tảng Tử Vi Đẩu Số tự host 100%, tiếng Việt, có thể kiểm chứng từng lời luận.

Không phải "chatbot biết tử vi". Hệ thống tách ba tầng trách nhiệm không bao giờ được trộn lẫn:

```text
Sự thật về lá số        =  deterministic engine (x-iztro)
Nguồn luận giải truyền thống =  knowledge / rules có provenance
Diễn đạt ngôn ngữ       =  LLM qua OpenAI-compatible API của chúng ta
```

**Invariant số 1:** LLM không bao giờ được tính lá số. LLM chỉ diễn giải từ facts + evidence do engine deterministic cung cấp.

## Nguyên tắc cốt lõi

- **100% self-host domain logic** — không runtime request nào tới Iztro/Renhuai/bên thứ ba. LLM chỉ gọi tới `AI_BASE_URL` do ta kiểm soát.
- **Deterministic trước, LLM sau** — lá số, tứ hóa, đại hạn, lưu niên đều do `x-iztro` tính; model chỉ đọc context đã compose.
- **Auditable** — mọi luận giải lưu kèm `EvidenceBundle`; người dùng có thể hỏi *"Vì sao hệ thống luận như vậy?"*.
- **Reproducible** — mọi chart/interpretation pin theo `engine_version + engine_profile + normalizer_version + knowledge_version + prompt_version + model`.
- **Ship sớm** — không RAG, không vector DB, không agent framework, không microservices ở V1.

## Stack đã freeze

| Layer | Chọn |
|---|---|
| Web | Next.js + React + TypeScript (UI port chọn lọc từ Renhuai) |
| Product API | FastAPI modular monolith, Python 3.12 |
| Ziwei engine | `x-iztro` 0.6.x (Rust core, Python binding) — canonical |
| Knowledge | x-iztro KnowledgePack (+ overlay packs sau) |
| Database | PostgreSQL (JSONB cho chart/evidence) |
| LLM | OpenAI-compatible endpoint của riêng ta (`AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL`) |
| Streaming | SSE |
| Oracle CI | JS `iztro` 2.6.1 (differential test, không phải runtime dep) |

## Tài liệu

| File | Nội dung |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Đặc tả kiến trúc & domain V2 |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Plan chi tiết theo phase/commit để bắt đầu code |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Evaluation gates & release criteria |
| [docs/DONORS.md](docs/DONORS.md) | Các repo OSS "donor" và phần lấy về |
| [docs/COUNCIL_REVIEW.md](docs/COUNCIL_REVIEW.md) | Kết quả council chuyên gia review & hướng đi đã chọn |
| [AGENTS.md](AGENTS.md) | Chỉ dẫn cho coding agent làm việc trong repo |

## Trạng thái

Đang ở bước **Vertical Slice V1** — xem [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
