# BUSINESS_RULES — Merch Agent

Các **quyết định nghiệp vụ** đã thống nhất (không hiển nhiên từ code). Đọc kèm code để review/điều chỉnh.
Mục `[GIẢ ĐỊNH]` = số/ngưỡng cần validate bằng dữ liệu thực tế VNGGames.

---

## Bước 1 — Intake (analysis.py)

- **Field bắt buộc** (`REQUIRED_FIELDS`, config.py): Mục đích, Chủ đề, Định vị, Target audience, Số lượng (bộ/suất), Deadline cần hàng, Budget. Thiếu → Status "Thiếu thông tin" (form đã required nên hiếm; chỉ là lưới an toàn).
- **Đánh giá deadline** (so critical-path, `assess_deadline`): ngưỡng ngày lịch `< 43` = **không khả thi**, `43–73` = **gấp**, `≥ 74` = **ổn** (= min31/avg53 ngày làm việc × 1.4). [GIẢ ĐỊNH] PIPELINE_WORKDAYS cần validate bằng 10-15 project history.
- **Deadline chỉ CẢNH BÁO, không chặn**: Status chỉ phụ thuộc thiếu/đủ thông tin.
- **Chống spam mail**: đủ field + deadline gấp/không khả thi → KHÔNG gửi mail riêng; ghi field "Cảnh báo deadline" → hiện **banner trong proposal + body mail proposal** (gộp 1 email).
- **Deadline không khả thi** → Bước 2 ép proposal **chỉ Catalogue (hàng có sẵn), bỏ creative** + giải thích.

## Bước 2 — Proposal (proposal.py)

### Chọn item dựa vào
1. **Đề bài** (build_brief): Game, Mục đích, Chủ đề, Định vị, Target, Số lượng, Deadline, Budget, Yêu cầu đặc biệt.
2. **Catalogue** (text mô tả — KHÔNG đưa ảnh vào LLM).
3. **Insight game (web-grounded)** — `game_insight()` qua Google Search (Gemini), định hướng đối tượng/phong cách. Giảm phụ thuộc catalogue (catalogue hiện không có metadata bổ sung).
4. **Phân khúc giá trị** (xem dưới).
> Việc chọn là **phán đoán ngữ nghĩa của model** — chưa có scoring/sales-data. Chất lượng phụ thuộc mô tả catalogue + insight.

### Số lượng & cơ cấu item
- **Số lượng item LINH HOẠT (thường 3-6)** theo ngân sách/bộ + độ phù hợp — không nhồi cho đủ. Tối thiểu 3 (ràng buộc trong vòng tự sửa budget).
- **Ưu tiên Catalogue trước** (có giá thật, nhanh); **Creative** chỉ lấp món catalogue thiếu.
- **Cap creative ≤ số catalogue** — giữ proposal đa số có giá để chốt được (creative = giá null → chờ báo giá vendor → nhiều quá thì khó chốt + lâu).
- **≥1 item key ⭐** (điểm nhấn).
- **so_luong mỗi item = Số lượng (bộ/suất)** ở đề bài; nếu < MOQ catalogue → nâng lên MOQ + ghi cảnh báo.

### Phân khúc giá trị (tier) — TỰ SUY (value_tier)
- **Ngân sách mỗi bộ quà = Budget ÷ Số lượng (bộ)** → suy phân khúc. Đây vừa là tier vừa là **trần tổng đơn giá/bộ**.
- Ngưỡng [GIẢ ĐỊNH 19/06 — chốt tạm để test, cần validate]:
  | Phân khúc | Ngân sách/bộ |
  |---|---|
  | Phổ thông | < 100.000đ |
  | Tầm trung | 100.000 – 500.000đ |
  | Cao cấp | > 500.000đ |
- Tier cao → ưu tiên item giá trị/thẩm mỹ cao (người nhận thấy xứng đáng); phổ thông → item thực dụng, có thể nhiều món.
- **KHÔNG hỏi requester nhập tier** (field "Định vị" gây khó hiểu) → tự suy cho khách quan; vẫn dùng Định vị/Mục đích/Target để chọn LOẠI item.

### Giá & budget
- **Giá catalogue cố định** lấy đúng từ bảng (`_enforce_catalogue_price`) — chống bịa giá. Tên không khớp catalogue → hạ thành creative.
- **Creative: don_gia = null** → hỏi vendor sau.
- Code tự tính tổng (không tin model cộng). **Vượt budget → tự sửa tối đa 2 vòng**; vẫn vượt → escalate PIC (không chốt).

### Yêu cầu đặc biệt (ràng buộc bắt buộc)
- AI chấm từng yêu cầu met/unmet, loại: item-bat-buoc / design-co-san / khac.
- **design-co-san LUÔN "met"** (dùng link design requester cấp, giá null) — không block vì chưa có giá.
- Có unmet → Status "Chờ làm rõ yêu cầu", hỏi requester; **tối đa 3 vòng làm rõ** → PIC.

### Minh bạch quyết định ("Cơ sở quyết định" trong proposal)
- Hiển thị để requester/sếp **đánh giá chất lượng → tìm hướng improve**:
  - **Phân khúc + ngân sách/bộ** (code tính, khách quan).
  - **Vì sao bộ này** (`co_so_quyet_dinh` — AI giải trình số lượng/cơ cấu/insight/ràng buộc).
  - **Insight game** (nguồn web, collapsible).

### Ảnh proposal
- **Item catalogue**: ảnh thật từ field "Hình ảnh mô tả" (nhúng base64).
- **Item creative**: ảnh concept/wireframe AI generate (gemini image) từ `goi_y_anh`.
- **Disclaimer trong proposal**: ảnh chỉ minh hoạ; **thành phẩm sẽ THIẾT KẾ RIÊNG theo nhận diện game** (màu/nhân vật/logo) sau khi chốt.
- ⚠️ **TODO bước sau**: cần bước "thiết kế theo game" giữa duyệt proposal và đặt vendor — mỗi item (vd ly giữ nhiệt) mỗi game 1 design khác. (Bước 3 / design phase.)

## Escalate PIC (tick "Cần PIC xử lý" + ghi "Lý do cần PIC")
4 trigger: (1) > 3 round proposal; (2) > 3 vòng làm rõ; (3) vượt budget sau 2 vòng tự sửa; (4) lỗi AI/LLM.
**Re-trigger** (PIC sửa gốc xong): untick "Cần PIC xử lý" + Status = "Mới tiếp nhận" → chạy lại từ Bước 1 (reset counters).

## Chi phí AI/proposal (tham khảo)
- Insight grounded: ~$0.035 (~900đ)/proposal · Ảnh creative: ~$0.039 (~1.000đ)/ảnh → ~2-3K/proposal.
