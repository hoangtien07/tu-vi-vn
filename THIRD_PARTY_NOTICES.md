# Third-Party Notices

Tử Vi VN tái sử dụng các thành phần mã nguồn mở sau. Danh mục đầy đủ quy
trình port/adapt nằm ở `docs/DONORS.md`.

## Ported / adapted content

| Thành phần | Nguồn | License | Ghi chú |
|---|---|---|---|
| `packages/knowledge/glossary-vi.md` | [x-haose/x-iztro](https://github.com/x-haose/x-iztro) 0.6.1 i18n table | MIT | Generated bởi `scripts/gen_glossary.py` — bảng thuật ngữ zh→vi |
| Knowledge excerpts trong EvidenceBundle | [x-haose/x-iztro](https://github.com/x-haose/x-iztro) 0.6.1 built-in KnowledgePack (zh-CN) | MIT | Runtime dependency, không vendored; nội dung excerpt được trích khi build context |
| Chart UI layout conventions | [Renhuai123/ziwei-doushu](https://github.com/Renhuai123/ziwei-doushu) | MIT | 12-palace grid + palace-cell layout inspired by Renhuai; code viết lại, không vendored |
| Differential test oracle | [SylarLong/iztro](https://github.com/SylarLong/iztro) 2.6.1 | MIT | Dev-only (`scripts/differential/`), không phải runtime dep |

## Runtime dependencies chính

| Package | License |
|---|---|
| x-iztro 0.6.1 (pinned) | MIT |
| FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, httpx | MIT / BSD |
| Next.js, React, Tailwind CSS | MIT |
| PostgreSQL 16 (docker-compose) | PostgreSQL License |

## Dataset (not distributed)

`Renhuai123/ziwei-doushu` Dataset v3 (~518k charts) — **không dùng trong
runtime**, không được phân phối kèm repo. License dataset: free incl.
commercial, attribution bắt buộc — xem `docs/DONORS.md`. Packs mined từ
dataset này (`eval/packs/vn-mined-*.json`, SPEC_V05) giữ attribution trong
`meta.source` của mỗi entry.
