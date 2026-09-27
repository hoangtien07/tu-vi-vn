# SPEC_DEPLOYMENT — tu-vi-vn production hosting (1–2 users)

Status: draft · Mục tiêu: self-host stack (FastAPI + Next.js + Postgres +
Caddy TLS) cho 1–2 người dùng, chi phí tối thiểu, giữ nguyên
`infra/docker-compose.yml` — không viết lại app.

## 0. TL;DR

| Hướng | Giá | Phù hợp khi |
|---|---|---|
| **A. Oracle Cloud Always Free (ARM VM)** | **$0** | Muốn free thật sự, chấp nhận vận hành VM |
| B. Hetzner CX22 (x86 VPS) | ~€3.8/tháng (~100k VND) | Muốn ổn định, ít lo capacity |
| C. Render free (hiện tại) | $0 | Chỉ demo — sleep + Postgres hết hạn 30 ngày |

Khuyến nghị: **A trước**; nếu Oracle hết capacity ARM ở region gần hoặc
muốn ổn định lâu dài → **B**. Render free giữ làm preview/staging.

## 1. Yêu cầu phi chức năng

- 1–2 người dùng → 1 VPS/VM duy nhất chạy cả stack là đủ.
- Dữ liệu Postgres phải persist + backup được (lá số là dữ liệu nhạy cảm).
- HTTPS bắt buộc (cookie `Secure`, SSE). Caddy tự lấy cert khi có domain;
  không domain → dùng nip.io/sslip.io (`<ip>.nip.io`).
- `AI_API_KEY` cấp qua `infra/.env`, không commit.
- Memory floor: api(uvicorn) ~200MB + web(next) ~200MB + postgres ~60MB →
  cần ≥1GB RAM thoải mái, 512MB rất căng (bài học Render).

## 2. Option A — Oracle Cloud Always Free

**Đủ điều kiện Always Free:** VM.Standard.E2.1.Micro (x86, 1GB) **hoặc**
Ampere A1 ARM (tới 4 OCPU / 24GB RAM — đề xuất 1 OCPU·4GB là dư sức).
200GB block volume free. Bandwidth 10TB/tháng free.

### Checklist triển khai

1. Tạo VM.Ampere A1 (Ubuntu 24.04 aarch64), mở inbound 80/443 (Security
   List + `ufw`), ghi public IP.
2. Cài Docker + compose plugin trên VM:
   `curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER`
3. `git clone` repo (hoặc `git pull` theo cron/deploy hook sau này).
4. `cp infra/env/.env.example infra/.env` → điền `POSTGRES_PASSWORD`
   (URL-safe), `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`.
5. `docker compose -f infra/docker-compose.yml up -d` → Caddy phục vụ
   `http://<ip>` ngay; gắn domain (hoặc `<ip>.nip.io`) để có HTTPS:
   sửa `infra/Caddyfile` `:80` → `<domain>` rồi `compose up -d` lại.
6. Cookie `Secure`: lật `secure=True` khi HTTPS sẵn (hardcode flag từ
   env — việc nhỏ, theo v0.4 hardening note trong `auth.py`).

### Backup

- Cron trên VM: `docker compose exec postgres pg_dump -U postgres tuvi |
  gzip > /backup/tuvi-$(date +%F).sql.gz`, giữ 14 bản, rsync/Object
  Storage free tier nếu muốn off-box.

### Rủi ro

- Capacity ARM hết tạm thời ở một số region → đổi region (Singapore/
  Osaka gần VN) hoặc x86 Micro (1GB — vẫn chạy được nếu enable swap).
- IP free tier đổi khi stop/start → dùng reserved public IP (free 2 cái)
  hoặc domain với DNS update.

## 3. Option B — Hetzner CX22 (~€3.8/tháng)

x86, 2 vCPU, 4GB RAM, 40GB, region Falkenstein — rẻ, ổn định, không lo
capacity. Triển khai **giống hệt checklist A** (bước 2–6). Snapshot
Hetzner (~€0.7/tháng) thay cho cron backup nếu muốn.

Alternatives tương đương: Contabo/Netcup/DO $4–6 — cùng playbook.

## 4. Option C — Giữ Render free (hiện trạng)

- Web OOM build → đã giảm bằng `.npmrc` concurrency (PR #37); nếu vẫn OOM
  chuyển web sang Render **static**: `next build` cần SSR nên không
  static-export được — sẽ cần native Node runtime (non-Docker, có build
  cache) hoặc tách web lên **Vercel free** (build không giới hạn RAM tương
  tự) còn api+db ở Render. Khi đó `API_INTERNAL_URL` → URL public của api.
- Postgres free hết hạn sau 30 ngày → phải export + tạo lại, hoặc upgrade
  $7. Không khuyến nghị làm production cho dữ liệu lá số.

## 5. Quyết định cần user

1. A (Oracle free) hay B (Hetzner ~€3.8)? Cần bạn tự tạo account +
   thanh toán/verify — tôi không có credentials.
2. Có domain sẵn không (để bật HTTPS + secure cookie)?

Sau khi chọn, tôi viết `infra/README.DEPLOY.md` (runbook đầy đủ từ VM
trống → app chạy HTTPS) trong PR tiếp theo.
