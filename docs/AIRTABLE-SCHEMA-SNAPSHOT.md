# Airtable Schema Snapshot — base "Merch Automation MVP" (`app46fhZ5wAv9LSzC`)

Chụp ngày 2026-06-17 để dựng lại base mới (account seat mới). Data records ở `airtable-snapshot-data.json`.

> **Quan trọng:** Agent tham chiếu field **bằng TÊN**. Dựng base mới **giữ đúng tên field** → agent chạy lại chỉ cần đổi env: `AIRTABLE_BASE_ID`, `AIRTABLE_TOKEN`, và `PROPOSAL_FILE_FIELD_ID` (field id "File proposal" của base mới — lấy lại sau khi tạo).
>
> **Link 2 chiều:** field `multipleRecordLinks` tạo từ 1 bảng → bảng kia tự sinh field link ngược. Chỉ cần tạo 1 phía (ghi rõ bên dưới), phía reverse xuất hiện tự động (rename cho gọn).
>
> **Theo plan hướng A:** base mới nên thêm field **"Created by"** (system) vào Projects làm requester (auto = current user); khi đó có thể BỎ field thủ công `Requester` + bridge `Requester (account)`. Field `Zalo ID` (Users/Vendors) là legacy — bỏ được.

---

## 1. Users (`tblpFR9z71M0arMkr`)
Nhân sự: requester, PIC, approver, head.

| Field | Type | Config |
|---|---|---|
| **Tên** ⭐primary | singleLineText | |
| Email | email | |
| Vai trò | singleSelect | Requester · Merch PIC · Approver · Head |
| Phòng ban / Game phụ trách | singleLineText | |
| Quản lý trực tiếp | singleLineText | |
| Tài khoản Airtable | singleCollaborator | account đăng nhập của user — cho interface filter current-user (gán tay) |
| _Projects_ (×2) | multipleRecordLinks | link ngược tự sinh từ Projects.Requester và Projects.Approver |

## 2. Vendors (`tblmWMyVpAhC6V8Se`)
Pool vendor sản xuất.

| Field | Type | Config |
|---|---|---|
| **Tên vendor** ⭐primary | singleLineText | |
| Email | email | |
| Chuyên môn | multipleSelects | May mặc · In ấn quà tặng · Phụ kiện · Gấu bông & Figure · Hàng điện tử có sẵn · Standee & POSM |
| Rating (1-5) | number | |
| Lead time lên mẫu | singleLineText | |
| Lead time sản xuất | singleLineText | |
| Ghi chú | multilineText | |
| Zalo ID | singleLineText | (legacy — bỏ được) |
| _Items_ | multipleRecordLinks | link ngược từ Items.Vendor |
| _Price History_ | multipleRecordLinks | link ngược từ Price History.Vendor |

## 3. Projects (`tblwMbfniEiNiPlPY`)
Mỗi record = 1 đề bài. **Bảng lõi agent đọc/ghi.**

| Field | Type | Config |
|---|---|---|
| **Tên project** ⭐primary | singleLineText | |
| Mã project | singleLineText | agent tự cấp MERCH-xxx |
| Game | singleSelect | Võ Lâm Chi Mộng [037] · PUBG Mobile [384] · Nikki VN [199] · CookieRun OvenSmash-VN [A24] · Valorant [465] · Võ Lâm Truyền Kỳ 1 Mobile · Võ Lâm Chi Mộng |
| Mục đích | multilineText | (required cho agent) |
| Chủ đề | singleLineText | (required) |
| Định vị | singleLineText | (required) |
| Target audience | singleLineText | (required) |
| Số lượng (bộ/suất) | number | (required) |
| Deadline cần hàng | date | (required) |
| Budget (VND) | currency | symbol ₫, precision 0 — (required) |
| Status | singleSelect | Mới tiếp nhận · Thiếu thông tin · Chờ duyệt items · Đã duyệt items · Chờ vendor báo giá · Chờ duyệt mẫu · Đang sản xuất · Đã giao hàng · Hoàn tất · Quá hạn duyệt |
| Phân loại merch | multipleSelects | Sản xuất mới · Mua sẵn · Giá trị cao >50tr |
| Requester | multipleRecordLinks → Users | (cân nhắc thay bằng "Created by") |
| Approver | multipleRecordLinks → Users | |
| Deadline phê duyệt | date | agent set hạn duyệt proposal |
| Phân tích AI | multilineText | agent ghi kết quả phân tích |
| Items | multipleRecordLinks → Items | |
| Duyệt proposal? | singleSelect | Duyệt · Cần sửa |
| Feedback proposal | multilineText | requester gõ yêu cầu sửa |
| Số round proposal | number | agent đếm vòng sửa (max 3) |
| File proposal | multipleAttachments | agent upload HTML proposal → Automation gửi mail |
| Cần PIC xử lý | checkbox | agent bật khi quá 3 round |
| Email requester | multipleLookupValues | lookup Requester → Users.Email (cho Automation "To") |
| Gửi phản hồi | checkbox | requester tick = commit → agent xử lý rồi tự bỏ tick |
| Requester (account) | singleCollaborator | agent điền từ Users."Tài khoản Airtable" (cho filter current-user; bỏ được nếu dùng Created by) |

## 4. Items (`tblCP9PjAQl1Rbg5I`)
Line items của project.

| Field | Type | Config |
|---|---|---|
| **Tên item** ⭐primary | singleLineText | |
| Project | multipleRecordLinks → Projects | |
| Loại | singleSelect | Áo thun · Hoodie · Áo khoác gió · Mũ lưỡi trai · Ly giữ nhiệt · Bình nước · Móc khóa · Sticker set · Túi tote · Standee · Gấu bông · Figure PVC · Tượng resin · Tai nghe bluetooth · Đèn ngủ 3D |
| Phân loại | singleSelect | Sản xuất mới · Mua sẵn · Giá trị cao >50tr |
| Chất liệu | singleLineText | |
| Kích thước | singleLineText | |
| Số lượng | number | |
| Đơn giá dự kiến (VND) | currency | ₫, precision 0 |
| Status | singleSelect | Đề xuất · Đã duyệt · Chờ báo giá · Đã có báo giá · Đang lên mẫu · Đang sản xuất · Hoàn tất |
| Vendor | multipleRecordLinks → Vendors | |
| Ghi chú AI | multilineText | |

## 5. Price History (`tbl1kjfoFbqMFeRG2`)
Lịch sử báo giá thật (48 records). _Lưu ý: redesign đã chuyển dùng Catalogue thay Price History cho AI #2 — bảng này có thể không cần ở base mới._

| Field | Type | Config |
|---|---|---|
| **Item** ⭐primary | singleLineText | |
| Loại | singleSelect | Áo thun · Hoodie · Áo khoác gió · Mũ lưỡi trai · Ly giữ nhiệt · Bình nước · Móc khóa · Sticker set · Túi tote · Standee · Gấu bông · Figure PVC · Tượng resin · Tai nghe bluetooth |
| Chất liệu | singleLineText | |
| Kích thước | singleLineText | |
| Số lượng đặt | number | |
| Đơn giá (VND) | currency | ₫, precision 0 |
| MOQ | number | |
| Vendor | multipleRecordLinks → Vendors | |
| Năm | singleSelect | 2024 · 2025 · 2026 |
| Game/Project gốc | singleLineText | |
| Ghi chú | multilineText | |

## 6. Catalogue (`tbl52nnBlKjYjEQNC`)
Sản phẩm có sẵn giá cố định — **nguồn AI #2 chọn item** (20 records). **Bảng quan trọng nhất cần repopulate.**

| Field | Type | Config |
|---|---|---|
| **Name** ⭐primary | singleLineText | |
| Miêu tả sản phẩm | multilineText | |
| Số lượng tối thiểu | singleLineText | MOQ dạng text tự do |
| Đơn giá | currency | ₫, precision 0 |
| Thời gian lên mẫu | singleLineText | |
| Thời gian sản xuất | singleLineText | |
| Xuất xứ | singleSelect | Trong nước · Nước ngoài |
| Link tham khảo | url | |
| Hình ảnh mô tả | multipleAttachments | (URL attachment cũ sẽ hết hạn — cần up lại ảnh) |

---

## Sau khi dựng base mới — checklist
- [ ] Tạo 6 bảng (hoặc 5 nếu bỏ Price History) + field đúng tên & type & options ở trên.
- [ ] Import data từ `airtable-snapshot-data.json` (ưu tiên Catalogue, Users, Vendors).
- [ ] Tạo PAT mới (scope `data.records:read/write` + `webhook:manage`) cho base mới.
- [ ] Lấy field id "File proposal" của base mới.
- [ ] Cập nhật env Coolify: `AIRTABLE_BASE_ID`, `AIRTABLE_TOKEN`, `PROPOSAL_FILE_FIELD_ID`.
- [ ] Đăng ký Airtable webhook mới (watch bảng Projects) trỏ endpoint agent.
- [ ] Dựng lại Interface (intake form + review) + Automations (gửi proposal "matches conditions", báo PIC).
