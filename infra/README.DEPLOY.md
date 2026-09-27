# Deploy tu-vi-vn trên VM tự quản (Oracle Always Free / Hetzner)

Runbook từ VM trống → app chạy. Toàn bộ stack đi qua `docker compose` —
postgres + migrate + api + web + caddy, không cần sửa app. Ước tính
đầu-cuối: ~30–45 phút. Yêu cầu VM ≥ 1GB RAM (khuyến nghị ≥ 2GB).

## 1. Tạo VM (Oracle console — phần duy nhất cần tài khoản của bạn)

1. cloud.oracle.com → **Create a VM instance**.
2. Image: **Ubuntu 24.04 (aarch64)**; Shape: **VM.Standard.A1.Flex** —
   1 OCPU / 4GB RAM (nằm trong Always Free; tới 4 OCPU/24GB tổng).
   Nếu ARM hết capacity ở region hiện tại → đổi region (Singapore/Osaka)
   hoặc dùng VM.Standard.E2.1.Micro (x86, 1GB — nên gắn swap).
3. Networking: VCN mặc định + public IPv4. Upload/gán SSH key của bạn.
4. Sau khi chạy: vào **Virtual Cloud Network → subnet → Security List**
   mở inbound TCP **80** và **443** (nếu dùng HTTPS/domain).
5. Ghi public IP.

> Hetzner CX22 thay thế: Ubuntu 24.04 x86, 2 vCPU/4GB — các bước sau giống
> hệt, chỉ khác phần console tạo máy.

## 2. Cài Docker trên VM

```bash
ssh ubuntu@<VM_IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
sudo apt-get update && sudo apt-get install -y ufw
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw --force enable
```

## 3. Clone + cấu hình

```bash
git clone https://github.com/hoangtien07/tu-vi-vn.git && cd tu-vi-vn
cp infra/env/.env.example infra/.env
```

Sửa `infra/.env` (chỉ giá trị bắt buộc):

```env
POSTGRES_PASSWORD=<chuỗi-ngẫu-nhiên-url-safe>   # vd: openssl rand -hex 24
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_API_KEY=<gemini-api-key>
AI_MODEL=gemini-3.1-flash-lite
AI_TIMEOUT_SECONDS=300
PORT=8080
# AUTH_COOKIE_SECURE=true  ← bật khi đã có HTTPS (bước 6)
```

## 4. Chạy

```bash
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml logs -f api   # chờ "Application startup complete"
curl http://localhost:8080/health   # {"status":"ok",...}
```

Mở `http://<VM_IP>:8080` — app chạy ngay qua Caddy (không cần sửa gì).
Postgres KHÔNG exposed ra ngoài; chỉ Caddy lắng port public.

## 5. Auto-update khi repo đổi (tuỳ chọn, khuyến nghị)

Cron rebuild mỗi 15 phút nếu main có commit mới:

```bash
(crontab -l; echo '*/15 * * * * cd ~/tu-vi-vn && git fetch -q origin main && [ $(git rev-parse HEAD) != $(git rev-parse origin/main) ] && git pull -q && docker compose -f infra/docker-compose.yml up -d --build') | crontab -
```

Hoặc tay: `git pull && docker compose -f infra/docker-compose.yml up -d --build`.
Alembic chạy ở service `migrate` mỗi lần `up` — migration tự apply.

## 6. HTTPS + secure cookie (khi có domain)

Trỏ DNS A-record của domain → `<VM_IP>` (hoặc dùng `<VM_IP>.nip.io` làm
domain tạm). Sửa `infra/Caddyfile` dòng đầu `:80` → `<domain>`:

```caddy
tuvi.example.com   # hoặc <VM_IP>.nip.io
```

Trong `infra/.env` đổi `AUTH_COOKIE_SECURE=true`. Rồi:

```bash
docker compose -f infra/docker-compose.yml up -d --force-recreate proxy api
```

Caddy tự cấp Let's Encrypt. Kiểm tra `https://<domain>` + cookie
`tv_session` có flag Secure trong DevTools → Application → Cookies.

## 7. Backup Postgres

```bash
mkdir -p ~/backup
(crontab -l; echo '0 3 * * * docker compose -f ~/tu-vi-vn/infra/docker-compose.yml exec -T postgres pg_dump -U postgres tuvi | gzip > ~/backup/tuvi-$(date +\%F).sql.gz && ls -t ~/backup/tuvi-*.sql.gz | tail -n +15 | xargs -r rm') | crontab -
```

Giữ 14 bản daily ở `~/backup`. Restore:

```bash
gunzip -c ~/backup/tuvi-<ngày>.sql.gz | docker compose -f infra/docker-compose.yml exec -T postgres psql -U postgres tuvi
```

## 8. Vận hành

- Xem logs: `docker compose -f infra/docker-compose.yml logs -f <api|web|postgres|proxy>`
- Restart 1 service: `docker compose -f infra/docker-compose.yml restart api`
- Disk: `docker system df` / dọn image cũ `docker image prune -a` (giữ volume `pgdata`!).

## Troubleshooting

| Triệu chứng | Kiểm tra |
|---|---|
| `/health` fail | `logs api` — thường DATABASE_URL/POSTGRES_PASSWORD sai hoặc migrate chưa xong |
| Web 502 | api chưa healthy: `docker compose ps` |
| Luận giải báo LLM lỗi | `AI_API_KEY`/`AI_MODEL`; Gemini free = 20 req/ngày/model |
| Cookie login không dính | đang HTTP mà `AUTH_COOKIE_SECURE=true` → tắt đi hoặc lên HTTPS |
| Build image chậm/OOM | VM 1GB → thêm swap 2GB: `fallocate -l 2G /swap && chmod 600 /swap && mkswap /swap && swapon /swap` |
