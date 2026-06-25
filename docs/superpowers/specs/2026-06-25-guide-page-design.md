# Trang /guide — Hướng dẫn sử dụng agent (quy trình) — Design

**Ngày:** 2026-06-25
**Mục tiêu:** Một trang web tự chứa `/guide` hướng dẫn người dùng vận hành merch-agent theo quy trình Bước 1→5, đủ chi tiết để **requester** và **PO/Merch PIC** tự làm được mà không cần hỏi dev.

## Bối cảnh & khoảng trống

Agent đã có 3 trang doc, nhưng không trang nào là "hướng dẫn sử dụng theo quy trình":

| Trang | Nội dung | Vai trò |
|---|---|---|
| `/flowchart` | Sơ đồ logic (mermaid) | Visual cho stakeholder — *không phải how-to* |
| `/rules` | Quy tắc ra proposal + ngưỡng + env config (mục ⑥) | Tài liệu tham chiếu |
| `/email-guide` | Sổ tay admin chỉnh template email | Hẹp (chỉ email) |

`/guide` lấp khoảng trống: **con người cần làm gì, ở bước nào, thao tác ra sao** — và link sang 3 trang trên thay vì chép lại.

## Cập nhật 25/06 (sau feedback khi review trang)

- **Đối tượng thực sự = người dùng cuối non-tech (người đặt merch).** Viết như tài liệu end-user, **bỏ mọi chi tiết kỹ thuật**: tên env var / bộ đếm vòng, mã email nội bộ (`clarify`/`bo_sung`…), tên field Airtable (`Gửi phản hồi`, `Duyệt proposal?`…), đường dẫn thô `?id=`.
- **Mô hình tương tác:** trừ **Merch PIC**, các vai khác (requester) **chỉ thao tác qua interface public (form/link trong email) hoặc xem read-only** — KHÔNG tự sửa/tích field trong Airtable. Bước 1 = requester **Submit form**, không "tích ô".
- Test đổi theo: `REQUIRED` chỉ giữ khung + nội dung user-facing; thêm `FORBIDDEN` chặn thuật ngữ kỹ thuật lọt vào trang.

## Quyết định đã chốt (qua brainstorm)

1. **Audience:** gộp 2 vai requester + PO/PIC trong 1 trang.
2. **Độ sâu:** đầy đủ + xử lý ngoại lệ (sổ tay vận hành thật), mô tả **chi tiết nhất** ở mọi bước (kể cả Bước 4 tự động).
3. **Cấu trúc:** trục chính theo **Bước (timeline 1→5)**; trong mỗi bước tách rõ việc của từng vai.
4. **Mức chi tiết:** **cụ thể** — gọi đích danh nút bấm, tên field Airtable, link Fillout, trích đoạn email thật.
5. **Triển khai:** trang HTML mới `docs/guide.html` + route `/guide`, style đồng bộ `/rules` + `/email-guide`.
6. Giữ cả 2 mục phụ cuối trang (Theo dõi tiến độ + FAQ sự cố).

## Kiến trúc

- **File nội dung:** `docs/guide.html` — HTML tĩnh tự chứa (inline CSS), giống `docs/proposal-rules.html` và `docs/email-guide.html`. Không template engine, không JS bắt buộc (trừ anchor scroll).
- **Route:** `main.py` thêm `@app.get("/guide")` trả `FileResponse(docs/guide.html, media_type="text/html")` — copy y khuôn route `/rules`, `/email-guide` hiện có.
- **Cross-link:** đầu trang có 3 nút sang `/flowchart`, `/rules`, `/email-guide`; ngược lại 3 trang kia thêm 1 nút sang `/guide` (điều hướng 2 chiều, để `/guide` thành hub).
- **Không đụng code nghiệp vụ** (pipeline/llm/airtable) — thuần tài liệu + 1 route + 4 nút link.

## Style (bám pattern sẵn có)

Lấy khuôn từ `docs/proposal-rules.html`: nền tối header, thân sáng, font sans-serif, bảng có border, badge/chip màu. Quy ước màu vai dùng xuyên suốt:
- 🟢 **Requester** (xanh lá)
- 🔵 **PO / Merch PIC** (xanh dương)
- 🤖 **Agent tự động** (xám)
- ⚠️ **Ngoại lệ / escalate** (cam/đỏ)
- ✉️ **Email** (tím)

## Nội dung trang

### Đầu trang
- Tiêu đề "Hướng dẫn sử dụng Merch Agent — Quy trình Bước 1→5".
- 1 đoạn "Trang này dành cho ai" (requester + PO/PIC) + chú giải 5 icon màu.
- Hàng nút link nhanh: **Sơ đồ logic** (`/flowchart`) · **Quy tắc & ngưỡng** (`/rules`) · **Chỉnh email** (`/email-guide`).
- Mục lục neo (anchor) tới 5 bước + 2 mục phụ.

### Thân bài — 5 khối theo timeline

Mỗi bước theo cùng một khuôn 6 phần:
> **🎯 Mục tiêu** → **🤖 Agent tự làm** → **🟢 Requester cần làm** (hộp thao tác: nút/field/link thật) → **🔵 PO/PIC cần làm** → **✉️ Email bắn ra** → **⚠️ Ngoại lệ & escalate**

**Bước 1 — Tiếp nhận & phân tích**
- Mục tiêu: tiếp nhận yêu cầu, thẩm định đủ thông tin để làm proposal.
- Agent: đọc record mới, kiểm tra 7 field cốt lõi (Mục đích, Chủ đề, Định vị, Target audience, Số lượng, Deadline cần hàng, Budget — theo `REQUIRED_FIELDS`).
- Requester: điền yêu cầu trên Airtable form; khi agent hỏi → cập nhật field rồi tích **`Gửi phản hồi`**.
- Email: `clarify` ("Cần trao đổi để hoàn thiện đề xuất").
- Ngoại lệ: thiếu thông tin → Status **`Chờ làm rõ yêu cầu`**, vòng làm rõ tối đa `MAX_CLARIFY_ROUNDS` (mặc định 3) → hết → **`Chờ Merch PIC`**.

**Bước 2 — Đề xuất (proposal) khả thi**
- Mục tiêu: ra proposal **chạy được thực tế** (đồng thời thỏa budget + deadline + yêu cầu đặc biệt).
- Agent: chọn item từ kho, tính chi phí + deadline lead-time; nếu không khả thi → tự sửa.
- Ngoại lệ (vòng điều chỉnh, dùng chung 1 bộ đếm `MAX_PROPOSAL_ROUNDS`):
  - Vượt budget → AI tự sửa 2 vòng, vẫn vượt → hỏi requester tăng budget / bỏ-rẻ hoá (Status `Chờ điều chỉnh`).
  - Trễ deadline → đề xuất phương án nhanh hoặc hỏi requester dời `Deadline cần hàng`.
- Email: `bo_sung` (bổ sung), hoặc `clarify`.

**Bước 3 — Duyệt proposal**
- Mục tiêu: requester chốt proposal.
- Requester: mở trang **`/proposal/{record_id}`** (link trong email) → bấm **Duyệt** hoặc **Cần sửa**; phản hồi qua form **Fillout** (field `Duyệt proposal?`, `Feedback proposal`).
- Email: `proposal` ("Mời duyệt proposal", có cảnh báo deadline + hạn duyệt).
- Ngoại lệ: quá `PROPOSAL_APPROVAL_DAYS` (mặc định 3) chưa duyệt → email `qua_han`; sửa quá `MAX_PROPOSAL_ROUNDS` → **`Chờ Merch PIC`**.
- Kết: Status **`Đã duyệt items`**.

**Bước 4 — Plan sản xuất** (tự động, vẫn mô tả đầy đủ)
- Mục tiêu: lập kế hoạch sản xuất + timeline.
- Agent: sinh file Excel plan, tính lead-time từng item (sản xuất song song → lấy max), ghi vào `File plan san xuat`.
- PO/PIC: nhận email, nắm plan; can thiệp nếu cần (NCC, lịch).
- Email: `plan` ("Plan sản xuất đã sẵn sàng" → team Merch).

**Bước 5 — Brief design & bàn giao**
- Mục tiêu: ra brief design, requester chốt, bàn giao team thiết kế.
- PO/PIC: bấm nút **`Bắt đầu design`** trên Airtable (chạy khi Status = `Đã duyệt items`).
- Agent: gom input (items + insight game + asset) → sinh brief PPTX → Status **`Chờ duyệt brief`** + lưu bản vào kho **Tài liệu dự án**.
- Requester: qua **link Fillout trong email brief** (form chung "Update requirement") → **Duyệt** / **Cần sửa** (+ `Feedback brief`) / **Tự upload** (`Brief tự upload`). Field `Duyệt brief?`.
- Email: `brief` (mời duyệt) → khi duyệt: `handoff_design` (gửi **PIC + requester**).
- Ngoại lệ: sửa quá `MAX_BRIEF_ROUNDS` (mặc định 3) → **`Chờ Merch PIC`**.
- Kết: Status **`Chờ thiết kế`**. (Bước 6 design review là phần sau, ghi rõ "ngoài phạm vi hiện tại".)

### Mục phụ 1 — 📊 Theo dõi tiến độ
Giải thích cách đọc trạng thái dự án: interface Kanban (theo Status) / Stepper / Timeline (Gantt theo Step Log, màu theo Nhóm mốc) đã build; kho **Tài liệu dự án** (grid) để xem lại mọi bản proposal/plan/brief có version.

### Mục phụ 2 — 🛠 Sự cố thường gặp (FAQ)
- Email không tới → kiểm tra địa chỉ requester + automation gửi mail.
- LLM lỗi → agent đặt Status `Cần PIC xử lý` / `Chờ Merch PIC` (xem email `pic`, field `Lý do cần PIC`).
- Link Fillout sai/không prefill → kiểm tra `?id=` = record id.
- Bảng nghĩa các Status: `Chờ làm rõ yêu cầu`, `Chờ điều chỉnh`, `Chờ duyệt items`, `Đã duyệt items`, `Chờ duyệt brief`, `Chờ thiết kế`, `Chờ Merch PIC` / `Cần PIC xử lý`, `Đã duyệt`.

## Nguồn dữ liệu (giá trị thật — đã verify)

- **Routes:** `/proposal/{record_id}`, `/flowchart`, `/rules`, `/email-guide`, `/guide` (mới) — `main.py`.
- **Email kinds:** `clarify`, `bo_sung`, `proposal`, `qua_han`, `plan`, `brief`, `handoff_design`, `pic` — `email_templates.py` + `pipeline.py`.
- **Statuses:** verify từ `pipeline.py` (liệt kê ở FAQ).
- **Fields người bấm:** `Gửi phản hồi`, `Duyệt proposal?`, `Feedback proposal`, `Bắt đầu design`, `Duyệt brief?`, `Feedback brief`, `Brief tự upload`.
- **Ngưỡng:** `MAX_CLARIFY_ROUNDS`, `MAX_PROPOSAL_ROUNDS`, `MAX_SUPPLEMENT_ROUNDS`, `MAX_BRIEF_ROUNDS`, `PROPOSAL_APPROVAL_DAYS` (mặc định 3) — `config.py`, chi tiết ở `/rules` mục ⑥.

## Phạm vi & YAGNI

**Trong phạm vi:** 1 file `docs/guide.html`, 1 route `/guide`, 4 nút link chéo (1 ở guide-hub ×3 đích + 3 nút "→ Hướng dẫn" ở các trang kia). Nội dung Bước 1→5 + 2 mục phụ.

**Ngoài phạm vi:** Bước 6 design review (chưa build — chỉ ghi 1 dòng "sắp có"); không sửa logic nghiệp vụ; không thêm i18n (chỉ tiếng Việt); không screenshot (dễ lỗi thời — dùng tên nút/field bằng chữ).

## Kiểm thử

- Smoke route: chạy app → `GET /guide` trả 200 + HTML; 3 nút link chéo trỏ đúng path.
- Đối chiếu giá trị: mọi tên field/status/email/ngưỡng trong trang khớp `config.py`/`pipeline.py`/`email_templates.py` (không bịa giá trị).
- Mở trên trình duyệt: mục lục neo nhảy đúng 7 mục; hiển thị ổn trên desktop.
