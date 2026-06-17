# Demo Runbook — Merch Agent (Team AMC)

Mục tiêu: demo live cho đội trưởng + quay video 2-3 phút một mạch.
Luồng demo: **Submit form → AI phân tích → Proposal HTML + email → Requester feedback → Agent sửa → Duyệt**.

> ✨ Agent đã deploy lên **GreenNode AgentBase (cloud)** và nối **Airtable webhook auto-trigger**.
> → KHÔNG cần chạy agent local, KHÔNG cần curl tay. Bạn chỉ thao tác trên Airtable, agent tự phản ứng sau vài giây.
> - Endpoint: `https://endpoint-41b865fc-901b-466e-a8ed-886b3c6df935.agentbase-runtime.aiplatform.vngcloud.vn`
> - Runtime: `merch-agent` (runtime-a3cd2059...)

---

## A. CHUẨN BỊ TRƯỚC KHI QUAY (làm xong rồi mới bấm record)

**1. Dọn dữ liệu test cũ** — ĐÃ DỌN (Projects = 0). Interface sạch, demo từ con số 0.

**2. Mở sẵn 3 tab trình duyệt, sắp xếp gọn:**
- **Tab 1**: Form nhập yêu cầu (eform) — `[ĐIỀN LINK FORM]`
- **Tab 2**: Interface duyệt proposal — `https://airtable.com/app46fhZ5wAv9LSzC/...`
- **Tab 3**: Gmail `phamtrungvinh263@gmail.com` (xem email agent gửi)

**3. (Tùy chọn) Kiểm tra agent cloud còn sống** — mở 1 tab gõ URL:
`https://endpoint-41b865fc-901b-466e-a8ed-886b3c6df935.agentbase-runtime.aiplatform.vngcloud.vn/health`
→ thấy phản hồi là OK. (Không cần show trong video.)

**4. Chuẩn bị sẵn nội dung sẽ gõ vào form** (để quay không bị khựng) — 1 đề bài ĐỦ thông tin (game của VNGGames):
- Tên project: `Sự kiện ra mắt phiên bản mới Võ Lâm Chi Mộng 2026`
- Game: `Võ Lâm Chi Mộng`
- Mục đích: `Quà tri ân game thủ và vật phẩm thương hiệu cho sự kiện offline ra mắt phiên bản mới, tăng gắn kết cộng đồng võ hiệp`
- Chủ đề: `Võ hiệp huyền ảo, môn phái giang hồ, tông màu mực tàu – vàng kim`
- Định vị: `Quà tri ân cho game thủ VIP/minh chủ + vật phẩm phát tại sự kiện offline`
- Target audience: `Game thủ 18–35 tuổi yêu thích võ hiệp, chơi mobile MMO nhập vai`
- Số lượng (bộ/suất): `500`
- Deadline cần hàng: `2026-09-30` (cách hôm nay >75 ngày → đánh giá "ổn", demo mượt)
- Budget (VND): `300000000`
- **Requester: chọn `Vinh Phạm`** ← bắt buộc, để email về hộp của bạn

**Content feedback (Cảnh 4 — khi demo "Cần sửa"):**
`Thêm 2-3 món cao cấp tặng minh chủ/khách VIP (ví dụ áo khoác thêu môn phái, bình giữ nhiệt khắc tên nhân vật), giảm bớt món giá rẻ. Ưu tiên item sưu tầm gắn với phiên bản mới.`

---

## B. KỊCH BẢN QUAY (theo cảnh — lời thoại + thao tác + kết quả mong đợi)

> Mẹo quay: sau mỗi thao tác trên Airtable, agent mất ~10-30s để xử lý (gọi AI). Khi quay, cứ nói lời thoại để "lấp" khoảng chờ; hoặc tạm dừng record, đợi xong rồi quay tiếp cảnh kết quả.

### Cảnh 0 — Mở đầu (~15s)
**Lời thoại:** "Đây là Merch Agent — trợ lý tự động hóa quy trình làm merchandise cho game của VNGGames, đang chạy trên nền tảng GreenNode AgentBase. Mình sẽ demo từ lúc một bạn Marketing gửi yêu cầu, cho tới khi chốt được danh mục sản phẩm, hoàn toàn tự động."
**Thao tác:** show tab Interface đang trống (chưa có project).

### Cảnh 1 — Gửi yêu cầu (~25s)
**Lời thoại:** "Bạn Marketing chỉ cần điền form yêu cầu này — không cần biết quy trình sản xuất."
**Thao tác:** sang tab Form, điền nhanh các field đã chuẩn bị (mục A.4), chọn Requester = Vinh Phạm → **Submit**.
**Kết quả:** form báo gửi thành công.

### Cảnh 2 — Agent tự phân tích + ra proposal (~35s)
**Lời thoại:** "Ngay khi có yêu cầu mới, agent tự động phân tích: kiểm tra đủ thông tin chưa, deadline có kịp không, rồi tự đề xuất danh mục sản phẩm dựa trên catalogue có sẵn cộng ý tưởng sáng tạo. Không ai bấm nút gì cả."
**Thao tác:** sang tab Interface, **đợi ~15-30s** (có thể F5/refresh). Record mới tự hiện ra.
**Kết quả:** record mới Status "Chờ duyệt items", có "Phân tích AI", có file proposal đính kèm, danh sách items.

### Cảnh 3 — Email proposal (~20s)
**Lời thoại:** "Người yêu cầu nhận ngay email kèm phiếu đề xuất dạng HTML — có hình ảnh sản phẩm, đơn giá, tổng chi phí trong ngân sách."
**Thao tác:** sang tab Gmail, mở email vừa tới, mở file proposal HTML (hoặc xem ngay trên Airtable record), cuộn cho thấy các item + tổng tiền.

### Cảnh 4 — Requester phản hồi, agent tự sửa (~30s)
**Lời thoại:** "Người yêu cầu duyệt hoặc góp ý ngay trên Airtable, không cần rep email qua lại. Ví dụ muốn đổi hướng sản phẩm."
**Thao tác:** trong Interface, mở record → set **Duyệt proposal? = Cần sửa** → dán **Feedback proposal** (content mục A.4) → tick **Gửi phản hồi** → **đợi ~15-30s**.
**Kết quả:** proposal tự tạo lại theo feedback, email mới gửi đi, file proposal cập nhật (vẫn chỉ 1 file), "Số round proposal" tăng lên 1.

### Cảnh 5 — Duyệt chốt (~25s)
**Lời thoại:** "Khi đã ưng, người yêu cầu bấm Duyệt. Agent tự chốt toàn bộ danh mục, chuyển sang bước mua hàng."
**Thao tác:** trong Interface → **Duyệt proposal? = Duyệt** → tick **Gửi phản hồi** → **đợi ~10s**.
**Kết quả:** Status đổi "Đã duyệt items", các item chuyển trạng thái "Đã duyệt".

### Cảnh 6 — Kết (~15s)
**Lời thoại:** "Toàn bộ quá trình từ yêu cầu tới chốt danh mục diễn ra trong vài phút, tự động hoàn toàn, chuẩn hóa, kiểm soát ngân sách, và lưu vết đầy đủ. Nếu sửa quá 3 vòng không chốt, agent tự động báo Merch PIC. Cảm ơn đã theo dõi."
**Thao tác:** show lại Interface với record "Đã duyệt items".

---

## C. LƯU Ý KHI QUAY
- **Quay màn hình:** `Cmd + Shift + 5` (sẵn trên Mac) → chọn vùng → Record. Hoặc OBS nếu cần webcam góc.
- **Tắt thông báo** (Do Not Disturb) để không lộ popup.
- **Khoảng chờ agent (~10-30s):** đây là lúc agent gọi AI thật. Có thể (a) vừa chờ vừa nói lời thoại, hoặc (b) tạm dừng record rồi quay tiếp khi xong → edit liền mạch.
- Auto-trigger qua Airtable webhook đã chạy thật (test PASS 2 lượt). Webhook hết hạn 23/06/2026 — nếu demo sau ngày đó cần đăng ký lại (báo mình).
- Nếu lỡ thao tác sai, dừng, sửa rồi quay lại cảnh đó (cắt edit sau).
- Upload: YouTube → **Unlisted** → lấy link dán vào form.

---

## D. CHECKLIST TRƯỚC KHI BẤM RECORD
- [ ] Agent cloud sống (`/health` trả OK) — đã ACTIVE
- [ ] 3 tab đã mở (Form / Interface / Gmail), sắp xếp gọn
- [ ] Nội dung form đã chuẩn bị sẵn (copy/paste nhanh)
- [ ] Requester = Vinh Phạm
- [ ] Gmail đăng nhập đúng phamtrungvinh263@gmail.com
- [ ] Do Not Disturb bật
- [ ] Dữ liệu test cũ đã dọn (Projects = 0 ✅)
