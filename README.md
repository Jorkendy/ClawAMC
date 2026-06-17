# merch-agent

Agent tự động hóa quy trình sản xuất merchandise VNGGames — HTTP server (FastAPI), self-host.

## Kiến trúc

```
Airtable (Merch Automation MVP)  ←→  merch-agent (FastAPI)  ←→  LiteLLM self-host
   form intake / duyệt proposal       POST /invocations          (gemini / claude / groq)
   (webhook tự kích agent)            GET  /health               qua Cloudflare Access
```

Luồng: requester submit form → Airtable webhook ping `/invocations` → agent **phân tích đề bài** (AI #1: đủ/thiếu thông tin + đánh giá deadline) → **đề xuất sản phẩm** từ Catalogue (AI #2: 80% catalogue + 20% creative, render HTML, upload Airtable) → requester duyệt/feedback ngay trên Airtable → agent sửa (tối đa 3 round) hoặc chốt; quá hạn → escalate Merch PIC.

## Actions (JSON body của `POST /invocations`)

| Payload | Mô tả |
|---|---|
| `{"webhook": "...", "base": "..."}` | Airtable webhook ping → chạy cả intake + xử lý duyệt (chạy nền, trả 200 ngay) |
| `{"action": "analyze_new"}` | Quét project status "Mới tiếp nhận" → phân tích |
| `{"action": "analyze_project", "project_code": "MERCH-001"}` | Phân tích 1 project |
| `{"action": "propose_items", "project_code": "..."}` | Sinh proposal items |
| `{"action": "send_proposal", "project_code": "..."}` | Propose + render HTML + upload + Status "Chờ duyệt items" |
| `{"action": "handle_proposal_decisions"}` | Xử lý requester duyệt/sửa (quét "Gửi phản hồi") |

## Env vars (`.env`)

Xem `.env.example`. Cần:
- `LLM_BASE_URL` — LiteLLM, vd `https://llm.vinhpham.com.vn/v1`
- `LLM_MODEL` — alias trong LiteLLM (`gemini-flash`, `gemini-pro`, `claude-sonnet`, `groq-oss`)
- `LLM_API_KEY` — virtual key riêng cho app này
- `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` — Cloudflare Access service token (nếu LLM endpoint sau Cloudflare Access)
- `AIRTABLE_TOKEN` — PAT (scope `data.records:read/write` + `webhook:manage`)
- `LLM_DISABLE_THINKING` — chỉ bật (`true`) khi backend là model Qwen hỗ trợ

> Cloudflare có thể chặn User-Agent "OpenAI/Python" (rule Block AI bots) → `llm_client.py` đã override User-Agent. Fix gọn hơn: thêm WAF skip rule cho request có service token hợp lệ.

## Chạy local

```bash
source venv/bin/activate
pip install -r requirements.txt
python3 main.py            # server http://127.0.0.1:8080

curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/invocations \
  -H "Content-Type: application/json" -d '{"action": "analyze_new"}'
```

## Deploy (Coolify)

Repo có `Dockerfile` → Coolify deploy thẳng:
1. New Resource → nguồn GitHub repo này → build type **Dockerfile**.
2. Expose port **8080**, healthcheck `GET /health`.
3. Set env vars (mục trên) trong Coolify UI — KHÔNG commit `.env`.
4. Đăng ký Airtable webhook trỏ vào `https://<domain-coolify>/invocations` (watch bảng Projects).
