# Step Log `end` → Gantt-bars + lead-time — Design Spec

**Ngày:** 2026-06-25
**Trạng thái:** Đã duyệt thiết kế — chờ user review → writing-plans.
**Bối cảnh:** Step & Progress phần B ([[merch-step-progress-plan]]). MVP (A) đã build: Step Log ghi `start` mỗi lần đổi bước → Timeline hiện **chấm**. Phần B làm Timeline thành **thanh** (có độ dài = thời gian mỗi bước) + tích **lead-time thật** để sau này validate hằng số deadline.

## 1. Mục tiêu & phạm vi
- **Mục tiêu:** mỗi dòng Step Log có `end` = thời điểm bắt đầu bước kế → formula `Lead-time (ngày)` (đã có) tự tính → Timeline vẽ thanh.
- **Phạm vi:** **go-forward only** — chỉ chốt `end` cho dòng sinh ra từ giờ. KHÔNG backfill 25 dòng cũ (đa số là data test/rác, project đã xoá → lead-time vô nghĩa).
- **Out of scope:** dọn rác Step Log cũ; mảng A (drive-steps/Bước 3+).

## 2. Ràng buộc
- Step Log nhận dòng mới từ **2 nguồn**: agent `log_event()` (sub-event plan/brief) + automation "Status đổi → ghi Step Log" (đổi Status). Giải pháp phải phủ cả 2 → dùng automation trigger "record created" (phủ mọi nguồn).
- Link `Project` có thể **gãy** (project bị xoá) → match dòng theo **`Mã project (text)`**, KHÔNG theo link.
- Lỗi render Timeline KHÔNG được chặn nghiệp vụ (dòng Step Log đã tạo trước đó).

## 3. Kiến trúc
**1 automation mới trên bảng Step Log** (`tblG4OGkyKAfUEfsj`):
- **Trigger:** When a record is created (Step Log).
- **Action: Run a script** —
  1. Input: `maProject` (= `Mã project (text)` của dòng vừa tạo), `startMoi` (= `start` dòng vừa tạo), `recordIdMoi` (id dòng vừa tạo, để loại trừ chính nó).
  2. Query Step Log toàn bảng (≤ vài trăm dòng — OK).
  3. Lọc các dòng có cùng `Mã project (text)` = `maProject`, `start` < `startMoi`, và id ≠ `recordIdMoi`.
  4. Lấy dòng có `start` lớn nhất → đó là **bước trước**.
  5. `updateRecordAsync` set `end` của bước trước = `startMoi`.
  6. Không có bước trước → bỏ qua (no-op).
  7. Toàn bộ trong try/catch — lỗi → log, không throw.

**Formula `Lead-time (ngày)`** (`fldov3ddeJr18EDcC`, đã tồn tại) tự tính `DATETIME_DIFF(end, start, 'days')` → không thêm field.

**Timeline view** "Step Log" trong Cổng Merch: cấu hình dùng `start` làm đầu thanh + `end` làm cuối thanh (hiện chỉ có start).

## 4. Data flow
Dòng Step Log mới tạo (log_event / status-automation) → automation "chốt end" fire → set `end` bước trước → Lead-time formula điền → Timeline vẽ thanh start→end.

## 5. Edge cases
- **Dòng đầu dự án** (không bước trước) → script no-op. ✅
- **Bước hiện tại** (chưa có bước kế) → `end` trống → Timeline hiện "đang diễn ra"; chốt khi status đổi tiếp. ✅
- **Rác/test cũ** → go-forward không đụng. ✅
- **2 dòng cùng project trùng `start`** (hiếm) → lấy 1, sai số không đáng kể.

## 6. Error handling
Script bọc try/catch; lỗi chỉ ảnh hưởng cosmetic Timeline. Automation run fail không ảnh hưởng pipeline (Step Log row đã có).

## 7. Test
- Đẩy 1 dự án (hoặc tạo tay) qua ≥2 status → dòng trước có `end`, `Lead-time (ngày)` ra số, Timeline thành thanh.
- Test step Run script trong Airtable (nút Test) với 1 dòng có bước trước.

## 8. Cần xác nhận khi build
- Field id `end` trên Step Log (lấy lúc writing-plans qua get_table_schema).
- Cách Timeline view nhận `end` (thao tác interface thủ công).
