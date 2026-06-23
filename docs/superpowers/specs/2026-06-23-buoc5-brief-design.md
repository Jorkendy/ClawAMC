# Bước 5 — Brief Design Generator (deck PPTX) — Design Spec

**Ngày:** 2026-06-23
**Trạng thái:** Đã chốt thiết kế (chờ writing-plans)
**Bối cảnh:** ClawAMC merch agent (Python/FastAPI, Coolify sandbox, base Airtable `appo1Oei5JvJ1EXAG`). Nối tiếp Bước 1–4 (intake → proposal → duyệt → plan sản xuất).

## 1. Vấn đề & mục tiêu

**Gap thực tế:** team thường đưa brief design mơ hồ / thiếu thông tin → designer phải hỏi lại nhiều → vỡ timeline design + sản xuất.

**Mục tiêu:** sau khi chốt items, agent tự sinh **một deck PowerPoint brief design** chất lượng tốt nhất có thể từ dữ liệu sẵn có (items đã chốt + insight game + asset project nếu có + text), **chủ động lấp khoảng trống và gắn nhãn nguồn**, để M&D có điểm khởi đầu rõ ràng (AI nháp → M&D hoàn thiện).

**Non-goals (MVP):**
- KHÔNG sinh file design final giao vendor (đó là việc M&D).
- KHÔNG tích hợp hệ thống ticket (Jira/ClickUp) — brief đưa M&D trực tiếp ngoài hệ thống.
- KHÔNG có vòng "Duyệt brief" / "Duyệt file design" (để sau; MVP chỉ ra deck + mail requester).
- KHÔNG kho asset chung theo game — asset đi theo từng project.

## 2. Quyết định đã chốt (brainstorm 23/06)

| Chủ đề | Quyết định |
|---|---|
| Cách dùng | Chạy **trong pipeline ClawAMC** (tự động hoá), input từ record Airtable |
| Xử lý input thiếu | AI **chủ động đề xuất + gắn nhãn** `(AI gợi ý)` vs `(Từ requester)` |
| Ảnh mockup | **Có cho mọi item** — tái dùng cache ảnh từ proposal, item chưa có thì sinh mới |
| Đầu ra | **`.pptx`** → upload field + **email requester** |
| Nhánh design | **AI nháp → M&D hoàn thiện** (deck do code sinh, không designer-grade) |
| Engine enrich | **Hướng B**: 1 LLM call enrich nội dung brief (không chỉ format lại proposal) |
| Trigger | **Nút "Bắt đầu design"** (PIC bấm sau khi xem plan) — không tự động |
| Asset | **Per-project** (field attachment trên Projects), thiếu → chạy bằng text + insight |

## 3. Kiến trúc

**Module mới `brief.py`** (song song `plan.py`), 2 hàm thuần (testable):
- `build_brief_content(fields, items, assets_status, insight) -> dict` — gọi 1 LLM JSON → nội dung brief đã enrich (per item + deck-level), mỗi trường gắn nguồn.
- `render_brief_pptx(brief, images, assets) -> bytes` — `python-pptx` render deck.

**Pipeline (`pipeline.py`):**
- `_generate_brief(record_id, code)` — fetch record + items + insight + asset → `build_brief_content` → gom ảnh → `render_brief_pptx` → `upload_brief` → clear cờ + ghi log.
- **`_scan_design_starts()`** (hàm scan riêng, tách khỏi `_scan_decisions` cho gọn): quét `{Bắt đầu design}=TRUE() AND {Status}="Đã duyệt items"` → gọi `_generate_brief` (bọc try/except mỗi record). Gọi trong `handle_proposal_decisions` (hoặc `on_webhook`), chung guard serialize `_run_guarded`.

**`proposal_render.py`:** thêm `upload_brief(record_id, pptx, code)` (tái dùng `_upload_attachment` generic, content-type pptx).

**`config.py`:** thêm `BRIEF_FILE_FIELD_ID` (+ env override).

**`requirements.txt`:** thêm `python-pptx`.

## 4. Trigger (nút "Bắt đầu design")

Dùng pattern flag sẵn có (như "Gửi phản hồi"):
1. Field checkbox **"Bắt đầu design"** trên Projects.
2. Nút "Bắt đầu design" (interface) set cờ = true (qua automation hoặc button run-automation).
3. Webhook ping → agent scan `{Bắt đầu design}=TRUE() AND {Status}="Đã duyệt items"`.
4. Sinh deck thành công → **clear cờ** (chống loop, cho phép bấm lại).
5. Guard: chỉ chạy khi Status="Đã duyệt items" (đã chốt items) — tránh chạy sớm.

## 5. Input handling

**Nguồn dữ liệu:**
- Items: từ field **"Proposal JSON"** (fallback bảng Items) — `ten, loai, nguon, chat_lieu, kich_thuoc, so_luong, yeu_cau_dac_biet, goi_y_anh, design_link, item_key`.
- Project fields: `Game, Mục đích, Chủ đề, Target audience, Yêu cầu đặc biệt`.
- **`game_insight`** (cache, tái dùng từ proposal) — định hướng visual khách quan.
- **Asset project** (attachment): `Logo game`, `Key Visual (KV)`, `Source material` — đọc trạng thái có/không + URL.

**Thiếu asset (thực tế hay gặp):** AI vẫn chạy từ text + insight; định hướng visual gắn `(AI gợi ý)`; deck ghi rõ *"Chưa có KV/Logo — cần cung cấp"*. Tool không bao giờ "đứng" vì thiếu asset.

## 6. Enrichment LLM (lõi chất lượng)

**1 LLM JSON call** (`ask_llm_json`). Output schema:

```
{
  "collection_name": str,           // tên bộ quà (AI đặt theo chủ đề/game)
  "overview": str,                  // 2-3 câu tổng quan bộ + định hướng chung
  "asset_status": str,              // tóm tắt asset có/thiếu
  "items": [{
    "ten": str, "loai": str,
    "idea": str,                    // concept + vibe + rationale
    "design_direction": str,        // hình dáng/cấu trúc, hoạ tiết, tông màu, nhân vật/biểu tượng
    "chat_lieu": str, "kich_thuoc": str,
    "yeu_cau_dac_biet": [str],
    "print_spec": str,              // vùng in, số màu, định dạng file cần (vd file vector AI, mockup)
    "references": [str],            // link từ input + loại ref AI gợi ý
    "sources": {                    // nguồn từng phần: "requester" | "ai"
      "idea": "requester|ai", "design_direction": "...", "chat_lieu": "...",
      "kich_thuoc": "...", "print_spec": "..."
    }
  }]
}
```

**Grounding (chống bịa):** dựa `game_insight` + dữ liệu proposal đã chốt; **KHÔNG bịa chi tiết logo/KV brand cụ thể**; định hướng visual suy từ insight + loại item; mọi suy luận đánh `sources=ai`. Trường lấy thẳng từ input (chất liệu/kích thước/yêu cầu requester đã ghi) → `sources=requester`.

## 7. Output `.pptx`

`render_brief_pptx(brief, images, assets)`:
- **Cover slide:** `collection_name`, game, project info (mã, số lượng, deadline), `overview`, `asset_status`, **chú giải** badge `(AI gợi ý)` vs `(Từ requester)`. KV/logo project làm nền/accent nếu có.
- **1 slide/item** (MVP, layout cố định): tiêu đề item → IDEA → DESIGN direction → Chất liệu + Kích thước → Yêu cầu đặc biệt → References → **ảnh mockup**. Mỗi mục có **badge màu** theo `sources` (xanh = requester, cam = AI gợi ý). Nội dung dài → để text box co chữ; KHÔNG tự tách slide 2 (python-pptx không auto-flow).
- **Ảnh:** map `{ten item → ảnh}`: tái dùng `_IMG_CACHE` của proposal (key `goi_y_anh` chuẩn hoá); item chưa có → `generate_image`. Lỗi tải/sinh → bỏ ảnh, vẫn render.

**Distribution:** `upload_brief` → field "File brief design" → clear cờ "Bắt đầu design" → Automation Airtable (user dựng) email requester (Created by) kèm deck.

## 8. Error handling

- **LLM lỗi** (JSON hỏng/rỗng): ghi note "Lịch sử chỉnh sửa" + **clear cờ** (cho bấm lại) — **KHÔNG escalate PIC** (brief không chặn luồng chính, khác lỗi ở Bước 1–2).
- **Ảnh lỗi:** skip ảnh đó, vẫn ra deck.
- **Upload lỗi:** `_upload_attachment` retry 3 lần (đã có); fail hẳn → note log, cờ giữ nguyên cho lần bấm sau.
- `_generate_brief` bọc try/except trong scan để 1 record lỗi không chặn record khác.

## 9. Thay đổi Airtable (Projects)

| Field | Type | Vai trò |
|---|---|---|
| File brief design | multipleAttachments | chứa deck `.pptx` (nguồn email) |
| Bắt đầu design | checkbox | cờ trigger (nút set, agent clear) |
| Logo game | multipleAttachments | asset per-project |
| Key Visual (KV) | multipleAttachments | asset per-project |
| Source material | multipleAttachments | asset per-project |

**User tự dựng (Airtable, ngoài code):** nút "Bắt đầu design" + Automation email requester (trigger `File brief design` not empty → To=Created by, đính kèm file).

## 10. Testing

- **Isolation** `build_brief_content`: mock `ask_llm_json` trả JSON mẫu → assert schema đầy đủ + nhãn nguồn.
- **Isolation** `render_brief_pptx`: input brief mẫu + ảnh stub → `python-pptx` ra file mở được (`load`), đủ số slide (cover + N item).
- **Smoke** import `pipeline` (wire `brief`, `upload_brief`).
- Giữ pattern test như `plan.py` (chạy bằng `./venv/bin/python`, stub network).

## 11. Giả định / việc còn lại

- `python-pptx` deck **không designer-grade** — bản nháp cho M&D. (Đã thống nhất.)
- Vòng "Duyệt brief" + "Duyệt file design" → giai đoạn sau.
- Layout deck bám tinh thần mẫu VAL (IDEA/DESIGN/chất liệu/kích thước/yêu cầu/source) — không sao chép visual.
- Asset đặt nền/accent: chỉ dùng asset project nạp; không tự chèn art nhân vật/KV brand.
