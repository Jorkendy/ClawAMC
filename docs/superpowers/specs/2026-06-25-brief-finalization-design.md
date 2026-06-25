# Bước 5 — Brief Finalization + Kho Tài liệu dự án — Design Spec

**Ngày:** 2026-06-25
**Trạng thái:** Đã duyệt thiết kế (3 phần) — chờ user review → writing-plans.
**Bối cảnh:** Step & Progress phần A ([[merch-step-progress-plan]], [[merch-brief-finalization-plan]]). Đây là **sub-project (1)**; sub-project (2) "Bước 6 Design review" tách riêng, làm sau. Ranh giới: (1) kết thúc ở bàn giao Status "Chờ thiết kế".

## 1. Mục tiêu
- Thêm **vòng duyệt brief**: requester Duyệt / Cần sửa (AI sửa) / Tự upload brief của họ.
- **Kho "Tài liệu dự án" chung**: lưu mọi bản tài liệu (proposal/plan/brief + requester upload) có version, để xem lại sau.
- **Tracking time mọi sự kiện** brief vào Step Log → timeline đầy đủ (gắn Gantt phần B).
- Duyệt xong → bàn giao: Status "Chờ thiết kế" + gửi brief cho PIC + requester.

## 2. Hiện trạng (điểm xuất phát)
`pipeline._generate_brief`: nút "Bắt đầu design" (Status "Đã duyệt items") → AI sinh PPTX → `upload_brief` vào field `File brief design` (xoá bản cũ trước) → mail `brief` cho requester → HẾT. CHƯA có duyệt brief / versioning / status design. Upload tập trung ở `proposal_render._upload_attachment` (dùng chung cho proposal/plan/brief), trả về response chứa URL attachment.

## 3. Ràng buộc & quyết định
- **Case 2 = cả 2 đường:** AI sửa theo feedback HOẶC requester tự upload. **"Duyệt brief" = cổng bàn giao DUY NHẤT** (tự upload chỉ thay file active, vẫn phải bấm Duyệt).
- **Versioning = bảng con `Tài liệu dự án`, lưu ATTACHMENT COPY** (option A). Giữ lịch sử trong Airtable = chấp nhận tốn storage (pptx brief nặng nhất); link/external storage (Drive) để dành spec sau nếu storage thành vấn đề.
- **Wire cả 3 doc** (proposal+plan+brief) vào kho ngay, DRY tại `proposal_render`.
- **MAX_BRIEF_ROUNDS = 3** → quá thì `Chờ Merch PIC` (mirror MAX_PROPOSAL_ROUNDS).
- Mirror chặt vòng duyệt proposal (`_scan_decisions`/`Duyệt proposal?`/`Feedback proposal`/`Số round proposal`/Fillout) để DRY + nhất quán UX.
- Mọi lỗi ghi kho/log KHÔNG chặn nghiệp vụ (try/except, log.warning).
- Local AIRTABLE_TOKEN read-only → live-verify sau deploy.

## 4. Schema Airtable

### 4.1 Bảng mới `Tài liệu dự án`
| Cột | Kiểu | Vai trò |
|---|---|---|
| Project | link → Projects | dự án |
| Mã project (text) | singleLineText | bền khi link gãy (như Step Log) |
| Loại | singleSelect: Proposal / Plan / Brief / Khác | loại tài liệu |
| Nguồn | singleSelect: AI / Requester | ai tạo |
| Phiên bản | number | v1, v2… (đếm theo loại trong project) |
| File | multipleAttachments | bản copy (giữ kể cả khi field gốc ghi đè) |
| Ghi chú | multilineText | feedback/round/context |
| Created | createdTime | tracking time |

### 4.2 Field mới trên Projects (mirror vòng proposal)
- `Duyệt brief?` — singleSelect: Duyệt / Cần sửa
- `Feedback brief` — multilineText
- `Brief tự upload` — multipleAttachments (requester đính file của họ)
- `Số round brief` — number
- *(tái dùng cờ `Gửi phản hồi` — route theo Status)*

### 4.3 Status thêm (field Status)
- `Chờ duyệt brief`
- `Chờ thiết kế`

## 5. State machine
```
Đã duyệt items ──[Bắt đầu design]──> _generate_brief
  → upload brief (auto log_document AI) → Status "Chờ duyệt brief"
  → log_event("Sinh brief") → mail brief (mời duyệt)

Tại "Chờ duyệt brief" + tick Gửi phản hồi:
  • Brief tự upload có file → snapshot thành File brief design (active)
       + log_document(Brief, Requester) + log_event("Requester tự upload brief") + clear field upload
       → vẫn "Chờ duyệt brief" (chờ bấm Duyệt)
  • Duyệt brief? = Duyệt → Status "Chờ thiết kế" + mail handoff_design (PIC+requester, kèm brief)
       + log_event("Duyệt brief → bàn giao thiết kế")   [RANH GIỚI sub-project 1]
  • Duyệt brief? = Cần sửa → _revise_brief(feedback)
```
`_revise_brief`: sinh lại brief theo `Feedback brief` → upload (auto log_document AI, version++) → `Số round brief`++ → nếu > 3 → Status `Chờ Merch PIC` + `Lý do cần PIC` + mail pic; else → "Chờ duyệt brief" + log_event("Sửa brief round N") + mail brief.

## 6. Code

### 6.1 `airtable_client.py`
`log_document(record_id, code, loai, nguon, file_url, filename, note="")`: tính version (đếm dòng cùng Project+Loại +1) → POST 1 dòng `Tài liệu dự án` (File = `[{"url": file_url, "filename": filename}]`, Mã project (text)=code, Created tự sinh). try/except → log.warning, không raise.

### 6.2 `proposal_render.py` (DRY hook)
`upload_proposal/upload_plan/upload_brief`: sau `_upload_attachment` thành công, lấy URL+filename từ response → gọi `log_document(loai, nguon="AI")`. → cả 3 doc tự vào kho. (Tách 1 helper nội bộ để không lặp.)

### 6.3 `pipeline.py`
- `_generate_brief`: sau `upload_brief` → `update_project(Status="Chờ duyệt brief", Email subject/body=render_email("brief"), "Số round brief"=0)` → `log_event("Sinh brief design")`. (Bỏ logic clear "Bắt đầu design" giữ nguyên.)
- `_revise_brief(record_id, code, feedback)`: gather inputs (kèm feedback vào prompt brief) → render → upload_brief → round = current+1; nếu > MAX_BRIEF_ROUNDS → escalate PIC (Status PIC_STATUS + Lý do cần PIC + render_email("pic") + log_event); else update_project(Status="Chờ duyệt brief", "Số round brief"=round, Feedback brief=None, Duyệt brief?=None, "Gửi phản hồi"=False, Email subject/body=render_email("brief")) + log_event("Sửa brief round N").
- Quét quyết định brief (thêm nhánh vào loop quét `Gửi phản hồi`, key theo Status "Chờ duyệt brief"):
  1. nếu `Brief tự upload` có file → đọc URL → set `File brief design` = file đó (active) + `log_document(Brief, Requester)` + `log_event` + clear `Brief tự upload`.
  2. nếu `Duyệt brief?` == Duyệt → `_handoff_design(record_id, code)`.
  3. nếu `Duyệt brief?` == Cần sửa → `_revise_brief(record_id, code, Feedback brief)`.
  4. clear `Gửi phản hồi` (+ `Duyệt brief?` khi đã xử lý xong nhánh duyệt/sửa).
- `_handoff_design(record_id, code)`: Status="Chờ thiết kế" + render_email("handoff_design") (ghi Email subject/body) + log_event("Duyệt brief → bàn giao thiết kế"). (Mail thực gửi do Automation Airtable theo cờ/status — xem §7.)

### 6.4 Brief revise prompt
`build_brief_content` nhận thêm `feedback` (optional) để AI sửa theo góp ý. (Mở rộng nhẹ hàm hiện có; nếu khó tách, thêm tham số mặc định None.)

## 7. Email (hệ template Airtable sẵn — [[merch-email-templates-plan]])
- Sửa dòng template `brief` (Subject/Body) → "Mời duyệt brief" + CTA (Duyệt / Cần sửa + feedback / tự upload). Vẫn render qua `render_email("brief", fields)`.
- Thêm dòng template **`handoff_design`** → người nhận PIC + requester, nội dung "Brief đã duyệt, chuyển sang thiết kế", kèm file brief.
- Automation Airtable: cần 1 automation gửi `handoff_design` (trigger Status="Chờ thiết kế") tới PIC + requester, đính `File brief design`. Brief "mời duyệt" tái dùng automation brief hiện có (đổi/giữ trigger phù hợp Status "Chờ duyệt brief").

## 8. Interface / Fillout (manual)
- Fillout "Update form": thêm section Status `Chờ duyệt brief` với `Duyệt brief?` (Duyệt/Cần sửa), `Feedback brief`, `Brief tự upload` (file upload), submit → tick `Gửi phản hồi`.
- Interface Cổng Merch: nút Duyệt brief / Cần sửa / Upload brief (mirror nút proposal). Page xem `Tài liệu dự án` (grid/list theo project) để review lịch sử.

## 9. Tracking time
Mọi sự kiện brief (sinh/sửa/upload/duyệt/bàn giao) gọi `log_event` → Step Log → Timeline/Gantt phần B tự vẽ + Nhóm mốc (map "Sinh brief…"/"Duyệt brief…" → nhóm "Đề xuất"; cân nhắc nhóm mới "Thiết kế" cho "Chờ thiết kế" — xem §11).

## 10. Error handling
- log_document / log_event lỗi → log.warning, không chặn.
- Snapshot requester upload lỗi → giữ nguyên trạng thái, không mất file gốc.
- Revise brief lỗi → mark PIC (như _mark_ai_error) thay vì kẹt im lặng.
- Cap 3 vòng → PIC (chống lặp vô hạn).

## 11. Test
- **Unit (pytest):** routing quyết định brief (Duyệt/Cần sửa/upload → nhánh đúng); đếm round + cap >3 → PIC; version tăng theo loại. Tách logic thuần khỏi I/O để test được (vd hàm quyết định trả "action").
- **Live smoke (sau deploy):** đẩy 1 dự án tới brief → Chờ duyệt brief → thử Cần sửa (AI sửa, version++ trong kho) → thử tự upload (kho ghi nguồn Requester) → Duyệt → Chờ thiết kế + mail PIC+requester; kiểm Step Log có đủ sự kiện + kho `Tài liệu dự án` đủ bản.

## 12. Cần xác nhận khi build
- Nhóm mốc cho Status mới: "Chờ duyệt brief"→"Đề xuất"? "Chờ thiết kế"→thêm nhóm "Thiết kế" (màu mới) hay gộp "Hoàn tất"? (chốt lúc plan — mặc định: thêm nhóm "Thiết kế").
- URL attachment từ upload-response có dùng trực tiếp tạo attachment ở bảng khác được không (nếu không → re-upload bytes vào kho). Verify lúc plan.
- Recipient PIC: dùng field `PIC phụ trách` (collaborator) — xác nhận có email.
