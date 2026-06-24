# Step & Progress (MVP A) — Design Spec

**Ngày:** 2026-06-24 · **Trạng thái:** chốt, đang triển khai
**Goal:** Cho PIC (và sau này requester) thấy 1 dự án merch đang ở **bước nào, từ khi nào, bước kế là gì / ai cần làm gì** — đọc từ field `Status` đã có. KHÔNG build workflow Bước 3+; downstream vẫn đổi Status thủ công, view chỉ phản ánh.

## Quyết định (brainstorm 24/06)
- **Platform:** toàn bộ **Airtable native** cho MVP — KHÔNG cần web. (Web `/progress/<record_id>` để dành khi cần phục vụ requester không seat; Portals official chưa có trên plan; ClientlyBase = bên thứ 3, loại vì data qua vendor lạ.)
- **Đối tượng MVP:** PIC/collaborator (đã có seat, vào được interface `Cổng Merch`). Requester-surface: ngoài scope MVP.
- **Granularity:** PIC xem đủ 8 bước happy path (Stepper theo `Status`); macro 5 mốc (`Mốc tiến độ`) để dành cho requester.
- **Timestamp:** bảng `Step Log` riêng (1 dòng/lần đổi bước), KHÔNG nhồi field ngày vào Projects.

## Kiến trúc dữ liệu (ĐÃ build qua API)
- **Bảng `Step Log`** (`tblG4OGkyKAfUEfsj`):
  - `Mã log` (text, primary) — nhãn vd "MERCH-001 · Đang sản xuất".
  - `Project` (link → Projects `tbltWsCRFMDAkpKKc`).
  - `Bước` (text) — tên Status mới.
  - `start` (dateTime, Asia/Ho_Chi_Minh) — lúc vào bước.
  - `end` (dateTime) — lúc rời bước (= lúc sang bước kế).
  - `Lead-time (ngày)` (formula) — `end - start`, để validate hằng số deadline.
- **Projects +2 formula** (đọc từ `Status` = `fldvIT2CbcSbJmO3O`):
  - `Mốc tiến độ` (`fldhZ7l1bpotxSPVg`) — gom 13 Status → 5 macro.
  - `Bước kế / ai làm gì` (`fldxgODPShdnvICb3`) — text hướng dẫn theo Status.

### Map 5 mốc (Mốc tiến độ)
1. **Tiếp nhận** ← Mới tiếp nhận · Thiếu thông tin · Chờ làm rõ yêu cầu
2. **Đề xuất & duyệt** ← Chờ duyệt items · Chờ điều chỉnh · Chờ Merch PIC · Quá hạn duyệt · Đã duyệt items
3. **Báo giá & mẫu** ← Chờ vendor báo giá · Chờ duyệt mẫu
4. **Sản xuất** ← Đang sản xuất
5. **Hoàn tất** ← Đã giao hàng · Hoàn tất

## Cần cấu hình trong UI (API không làm được)
### 1. Automation: "Status đổi → ghi Step Log"
- **Trigger:** When record updated · table Projects · watch field `Status`.
- **Action A — Find records:** Step Log nơi `Project` = record trigger AND `end` is empty (dòng bước cũ còn mở).
- **Action B — Update record:** với dòng tìm được (nếu có) → set `end` = "Actual run time" của trigger.
- **Action C — Create record** trong Step Log: `Project` = record trigger · `Bước` = giá trị `Status` mới · `start` = Actual run time · `Mã log` = `<Mã project> · <Status>`.
- (Fire cả khi agent đổi Status qua API.)

### 2. PIC views trong interface `Cổng Merch`
- **Kanban** element by `Status` → bảng tổng "dự án nào ở bước nào". (Editable = kéo card đổi bước — chính là Approach B, để mở sau.)
- **Stepper:** record-detail page, field `Status` đặt appearance = **Stepper** (View-only) + hiện `Bước kế / ai làm gì` + danh sách Step Log (timeline).
- **Timeline/Gantt:** element Timeline trỏ `Step Log`, filter theo 1 project, dùng `start`/`end` → Gantt các bước. (Gantt theo kế hoạch sản xuất = optional sau.)

## Synergy
`Step Log.Lead-time` → lead-time THẬT mỗi bước → validate hằng số deadline (overhead 27 / ×1.4 / creative 8-25), đạt mục tiêu "70-80% tin cậy" đang treo.

## Ngoài scope
- Requester-surface (web `/progress` hoặc Portals).
- Drive-steps (B): CTA đổi bước + build workflow Bước 3+ thực (vendor báo giá → ... → hoàn tất).

## Test
1. Đổi `Status` 1 project thật → Step Log có dòng mới, `start` đúng, dòng cũ được set `end`.
2. `Mốc tiến độ` + `Bước kế / ai làm gì` hiển đúng theo Status.
3. Kanban gom đúng cột; Stepper hiển đúng bước; Timeline vẽ đúng bars.
