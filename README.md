# merch-agent

Agent tự động hóa quy trình sản xuất merchandise VNGGames — chạy trên GreenNode AgentBase.

(README gốc của bộ skill agentbase được giữ tại `AGENTBASE-SKILLS-README.md`)

## Kiến trúc

```
Airtable (Merch Automation MVP)  ←→  merch-agent (AgentBase Custom)  ←→  GreenNode LLM (Qwen 3.5 27B)
       form intake / tracking              POST /invocations                phân tích đề bài
                                                 │
                                          Zalo Bot (phiếu duyệt reply-lệnh)
                                          Gmail (mail loop vendor) — ngày 5
```

## Actions hiện có

| Payload | Mô tả |
|---|---|
| `{"action": "analyze_new"}` | Quét mọi project status "Mới tiếp nhận", phân tích từng cái |
| `{"action": "analyze_project", "project_code": "MERCH-001"}` | Phân tích 1 project cụ thể |

Mỗi lần phân tích: chấm đủ/thiếu 7 thông tin bắt buộc → đánh giá deadline theo lead time (Sản xuất mới 30d / Mua sẵn 10d / Giá trị cao 60d) → phân loại 3 nhóm merch → ghi field "Phân tích AI" + đổi Status → thiếu thông tin thì kèm draft mail gửi requester.

## Chạy local

```bash
source venv/bin/activate
python3 main.py   # server tại http://127.0.0.1:8080

# test
curl -X POST http://127.0.0.1:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"action": "analyze_project", "project_code": "MERCH-002"}'

curl http://127.0.0.1:8080/health
```

## Env vars (.env)

Xem `.env.example`. Cần: `LLM_API_KEY` (GreenNode AIP — tạo qua `/agentbase-llm`), `LLM_BASE_URL`, `LLM_MODEL`, `AIRTABLE_TOKEN` (PAT tạo tại https://airtable.com/create/tokens, scope `data.records:read` + `data.records:write` trên base Merch Automation MVP).

## Deploy

Dùng `/agentbase-deploy` (build Docker → push Container Registry → tạo Runtime).

## Test scripts khác

- `zalo_bot_test/test_zalo_bot.py` — go/no-go Zalo Bot Platform
- `zalo_bot_test/test_zalo_approve_text.py` — flow phiếu duyệt reply-lệnh qua Zalo
