# Kịch bản test — Cổng Merch (base mới, hướng A)

Mỗi TC: **Thao tác → Kết quả mong đợi**. Phần agent (~20-30s) là agent gọi LLM, chờ chút.

## Data submit (dùng cho TC1)
```
Tên project:        Sự kiện ra mắt phiên bản mới Võ Lâm Chi Mộng 2026
Game:               Võ Lâm Chi Mộng
Mục đích:           Quà tri ân game thủ và vật phẩm cho sự kiện offline ra mắt phiên bản mới
Chủ đề:             Võ hiệp huyền ảo, môn phái giang hồ, tông mực tàu – vàng kim
Định vị:            Quà tri ân cho game thủ VIP + vật phẩm phát tại sự kiện
Target audience:    Game thủ 18–35 yêu võ hiệp, chơi mobile MMO
Số lượng (bộ/suất): 500
Deadline cần hàng:  2026-09-30
Budget (VND):       300000000
```

---

## TC1 — Submit form (intake + auto proposal)
- **Thao tác:** Đăng nhập → tab "Gửi yêu cầu" → điền 9 field → Gửi yêu cầu.
- **Mong đợi:** Form báo gửi thành công. Sau ~20-30s, tab "Yêu cầu của tôi" hiện 1 record: Status **"Chờ duyệt items"**, có Mã MERCH-xxx, **File proposal** (mở xem được), **Phân tích AI** (gọn, không lặp). Created by = bạn.

## TC2 — Xem proposal
- **Thao tác:** Mở record → mở **File proposal** (HTML).
- **Mong đợi:** Thấy danh sách items (catalogue + creative), đơn giá, tổng tiền ≤ budget, nhận xét.

## TC3 — Phản hồi sửa (Cần sửa)
- **Thao tác:** Chọn **Duyệt proposal? = Cần sửa** → gõ **Feedback** (vd "Thêm 2 món cao cấp tặng VIP") → bấm nút **Gửi**.
- **Mong đợi:** Record **biến khỏi list** ~20-30s (đang xử lý). Sau đó hiện lại: proposal mới (items đổi theo feedback), **Số round = 1**, **Lịch sử chỉnh sửa** có "Round 1 — sửa theo feedback: ...". (Items vẫn ~5, KHÔNG nhân loạn.)

## TC4 — Chống spam / feedback giữa chừng (Q1/Q2)
- **Thao tác:** Ngay sau khi bấm Gửi (đang xử lý), thử tìm/mở lại record hoặc bấm lại.
- **Mong đợi:** Record đã **ẩn khỏi list** (filter Gửi phản hồi=checked) → không thao tác được → không spam, không gửi feedback 2 chồng lên. Hiện lại khi xong.

## TC5 — Duyệt (Approve)
- **Thao tác:** Chọn **Duyệt proposal? = Duyệt** → bấm Gửi.
- **Mong đợi:** Status **"Đã duyệt items"**, các item chuyển "Đã duyệt", Lịch sử có "Requester đã DUYỆT".

## TC6 — Guard sau khi đã duyệt
- **Thao tác:** Trên record đã duyệt, lại chọn Cần sửa + feedback → Gửi (nếu còn thao tác được).
- **Mong đợi:** Agent **bỏ qua** — Status vẫn "Đã duyệt items", round không tăng, không tạo lại proposal.

## TC7 — Cô lập per-user
- **Thao tác:** Đăng nhập account **alias thứ 2** (cửa sổ ẩn danh) → mở "Yêu cầu của tôi".
- **Mong đợi:** KHÔNG thấy record của user 1. Submit form bằng user 2 → chỉ user 2 thấy record của mình.

## TC8 — Escalation 3 round *(cần: 1 row Users = Merch PIC + Automation "Báo PIC")*
- **Thao tác:** Trên 1 record, Cần sửa 3 lần liên tiếp (round 1→2→3), rồi feedback lần 4.
- **Mong đợi:** Round vượt 3 → **Cần PIC xử lý = true**; (nếu có Automation) PIC nhận mail.

## TC9 — Email proposal *(cần: Automation "gửi mail" matches conditions)*
- **Mong đợi:** Mỗi lần proposal mới (TC1, TC3) → requester nhận **email** kèm File proposal.

---

## Mình verify song song (qua API)
Khi bạn chạy TC1–TC7, báo mình → mình check data: Created by đúng, Status/round/items đúng, Lịch sử chỉnh sửa, không churn, cô lập. TC8/TC9 cần setup thêm (PIC row + automations) mới test được.
