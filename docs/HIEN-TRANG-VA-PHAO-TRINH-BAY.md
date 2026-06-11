# MERCH AGENT — HIỆN TRẠNG & PHAO TRÌNH BÀY
*Cập nhật: 11/06/2026 — sau khi hoàn thành golden path MVP + test form thật*

---

## 1. BÀI TOÁN (30 giây mở đầu)

VNGGames sản xuất hàng trăm items merch/năm cho nhiều game. Quy trình 17 bước từ nhận đề bài đến thanh toán đang chạy **thủ công** → nhân sự overload mùa cao điểm, dễ sót thông tin, và **nhân sự mới (fresh) không đủ kiến thức nguyên vật liệu/giá** để làm việc với vendor.

**Giải pháp:** AI agent điều phối toàn trình trên 3 nền tảng nhân viên + vendor VN đã dùng sẵn: **Airtable** (nguồn sự thật) + **Zalo** (giao tiếp & phê duyệt) + **GreenNode LLM** (bộ não phân tích). Agent gánh phần *kiến thức* (giá lịch sử, chất liệu, lead time, soạn thảo), người giữ phần *quyết định* (duyệt items, duyệt giá, duyệt mẫu).

---

## 2. KIẾN TRÚC & STACK — KÈM LÝ DO (phần sếp hay hỏi "tại sao")

```
Requester ──Form Airtable──► Airtable Base (nguồn sự thật duy nhất)
                                  │ webhook (record mới → ping)
                                  ▼
                     merch-agent (Python, GreenNode AgentBase Custom)
                     POST /invocations + GET /health + 2 thread nền
                      │                │                  │
              GreenNode LLM      Zalo Bot API        Reminder 6h/lần
              (Qwen 3.5 27B)    (phiếu duyệt +       (nhắc + escalate)
              phân tích/parse    RFQ vendor)
```

| Lựa chọn | Lý do (trả lời khi bị hỏi) |
|---|---|
| **Airtable** | Có MCP chính thức + Webhooks API + form/interface dựng trong vài phút; team merch non-tech tự sửa được data. Free tier KHÔNG đủ (1.000 API calls + 100 automation runs/tháng) → dùng Team trial/plan. |
| **Zalo (không phải Telegram)** | Telegram bị chặn tại VN từ 5/2025 (truy cập chập chờn) — không công ty VN nào duyệt làm tool chính thức. Zalo là sản phẩm VNG + 100% nhân viên & vendor VN dùng sẵn. Kỹ thuật Telegram tốt hơn, nhưng đã thiết kế adapter — swap kênh không đổi logic. |
| **Zalo (không phải Teams)** | Teams cần Entra app + admin consent tenant (xin IT lâu), và vendor ngoài không có Teams. Teams nằm trong roadmap production cho khối văn phòng. |
| **Bỏ mail khỏi MVP** | Quyết định scope có chủ đích: vendor VN chốt giá qua Zalo là thực tế phổ biến. Mail (Outlook/Graph API, shared mailbox + match reply bằng mã [MERCH-x] trong subject) nằm trong roadmap cho vendor lớn/audit trail. |
| **GreenNode LLM, model Qwen 3.5 27B** | Định hướng hackathon: dùng hạ tầng nhà (VNG Cloud). Qwen 3.5 27B **miễn phí**, mạnh tiếng Việt (201 ngôn ngữ), đủ cho task phân tích/trích xuất. Model chỉ là 1 biến config — đổi sang MiniMax M2.5 mất 10 giây nếu cần chất lượng cao hơn. Lưu ý kỹ thuật: phải tắt thinking mode (`chat_template_kwargs: enable_thinking=false`) không thì token bị nướng vào reasoning. |
| **AgentBase Custom framework (không phải LangChain/LangGraph)** | Logic của ta là orchestration tuần tự + gọi LLM một phát một — không cần agent-with-tools framework. Ít tầng = dễ debug trong 7 ngày. Vẫn đóng Docker deploy được lên AgentBase Runtime (output bắt buộc của hackathon). |
| **Webhook (không polling Airtable)** | Polling 1 phút/lần = 1.440 calls/ngày, đốt sạch quota. Airtable Webhooks API push ping → agent chỉ gọi API khi có sự kiện thật. Polling chỉ còn ở Zalo getUpdates (bắt buộc, không có lựa chọn khác cho bot Zalo local). |

**Repo:** `ClawAMC/` — main.py (~750 dòng), Dockerfile (python:3.13-slim), requirements (greennode-agentbase, openai, python-dotenv). Base Airtable: `app46fhZ5wAv9LSzC` (5 bảng: Projects, Items, Price History 48 dòng, Vendors 5, Users 4).

---

## 3. NHỮNG GÌ ĐÃ CHẠY ĐƯỢC (đã test THẬT, không mock)

### Vòng đời một project (state machine)

```
Form submit (status trống) ──tự động──► Phân tích AI
  ├─ thiếu thông tin / deadline gấp → "Thiếu thông tin" + DRAFT MAIL hỏi requester
  └─ đủ → "Chờ duyệt items" ──tự động──► Proposal items + giá ──tự động──► Phiếu duyệt Zalo
        Approver reply "1" → "Đã duyệt items" + audit log ──tự động──► RFQ đến từng vendor (Zalo)
        Vendor nhắn giá tự do → AI parse → điền Items → đủ giá TOÀN BỘ items → "Chờ duyệt mẫu" + báo PIC
  + Reminder 6h/lần: quá hạn duyệt → "Quá hạn duyệt" + nhắc approver; ≥3 ngày → escalate manager
```

### Năng lực AI đã chứng minh qua test

1. **Phân tích đề bài:** chấm đủ/thiếu 7 thông tin bắt buộc; đánh giá deadline theo lead time nghiệp vụ (Sản xuất mới ≥30 ngày, Mua sẵn ≥10, Giá trị cao >50tr ≥60); phân loại 3 nhóm merch (có quy tắc cứng: "Giá trị cao" = có MÓN >50tr, ước lượng budget÷số lượng — đã vá lỗi gán nhãn bừa theo chữ "premium"); soạn mail bổ sung thông tin tiếng Việt chuẩn nghiệp vụ.
2. **Proposal + báo giá dự kiến:** tra 48 dòng Price History có TRÍCH DẪN dòng nào, cộng trượt giá ~9%/năm, chọn mức số lượng gần nhất (đã vá lỗi chọn dòng SL lớn cho rẻ), cảnh báo MOQ, chọn vendor theo chuyên môn + rating (né vendor 2.8★ từng trễ hạn). **Vòng tự sửa budget:** code Python tính tổng (không tin số model) — MERCH-001 từ 481tr tự sửa 2 vòng về 245.2tr/250tr với chiến lược thông minh (figure limited 100c cho top user + gấu bông đại trà).
3. **Chống bịa giá (anti-hallucination):** item không có history (test: đèn ngủ 3D) → `don_gia: null` + "Chưa có dữ liệu giá — cần hỏi vendor". TUYỆT ĐỐI không đoán.
4. **Phê duyệt qua Zalo:** phiếu reply 1/2 (Zalo Bot KHÔNG có nút bấm — xem mục 5), danh tính verified từ platform (`from.id`), audit log "DUYỆT bởi Vinh Phạm (id) lúc 16:04" vào record. Approval matrix nằm trong bảng Users (đổi người duyệt = sửa data, không sửa code). Fallback: form không chọn approver → quản lý của requester → không có thì Merch PIC triage.
5. **Parse báo giá vendor dạng chat tự nhiên:** hiểu "685k" = 685.000đ, "1 tuần" = lead time; match item theo tên gần đúng nhưng KHÔNG match bừa (vendor báo "áo thun" khi đơn chỉ có "áo khoác gió" → không nhận); tách điều kiện thương mại (phí khuôn 25tr, cọc 50%) vào ghi chú; vendor nhắn nhầm đơn → bot liệt kê lại items đúng và giữ phiên; track chính xác items còn thiếu giá.

### Các phiên test thật đã chạy (kể được khi bị hỏi "test chưa?")

- 4 case thiết kế: MERCH-001 (đủ thông tin), 002 (thiếu 3 trường), 003 (deadline 10 ngày — AI bác), 004 (mix 3 loại merch) — đều đúng kỳ vọng
- Test chống bịa giá đèn ngủ 3D — PASS
- E2E giả lập MERCH-009: form giả → phân tích → proposal → duyệt → RFQ → vendor reply — PASS, kể cả pha nhắn nhầm đơn
- **E2E form THẬT MERCH-010:** submit form Airtable thật → toàn trình tự chạy đến vendor quote. Lộ và vá 3 bug thật: form ẩn Status → record trống status bị agent lờ; form ẩn Mã project → tự cấp mã; form trống Requester/Approver → fallback PIC

---

## 3.5 AI ĐƯỢC DÙNG Ở ĐÂU, DÙNG THẾ NÀO — GIẢI THÍCH CHO NGƯỜI KHÔNG LÀM TECH

**Cách hình dung đơn giản nhất:** AI ở đây giống một **nhân viên tư vấn merch dày dạn kinh nghiệm nhưng làm việc theo kỷ luật chặt**. Mỗi lần cần nó, hệ thống "đặt lên bàn" cho nó đúng những tài liệu cần thiết (đề bài, sổ giá cũ, hồ sơ vendor...), yêu cầu nó trả lời **theo đúng biểu mẫu** để máy đọc được, và mọi kết quả đều ghi vào Airtable cho người kiểm tra. AI **không tự lên mạng tìm gì, không tự quyết gì** — chỉ được dùng những gì được đưa, và đề xuất của nó luôn dừng lại ở cửa phê duyệt của con người.

Toàn hệ thống có đúng **3 điểm dùng AI**. Mọi thứ còn lại là máy chạy quy tắc cứng (như Excel chạy công thức — đúng tuyệt đối, không "suy nghĩ").

### Điểm AI #1 — Đọc hiểu đề bài (khi requester gửi form)

| | Nội dung |
|---|---|
| **AI được đưa gì (input)** | (1) Toàn bộ nội dung form requester điền (tên project, game, mục đích, chủ đề, định vị, đối tượng, số lượng, deadline, budget); (2) hôm nay là ngày mấy + còn bao nhiêu ngày đến deadline — **do máy tính sẵn, AI không tự tính ngày** (AI tính toán ngày tháng hay sai); (3) danh sách trường bị bỏ trống — **máy kiểm sẵn**; (4) bảng quy tắc nghiệp vụ: làm mới cần tối thiểu 30 ngày, mua sẵn 10 ngày, hàng cao cấp 60 ngày. |
| **AI làm gì** | Đọc hiểu như một người có nghề: đề bài này thuộc nhóm nào (làm mới / mua sẵn / cao cấp), deadline có kịp không và vì sao, đề bài muốn gì, nên đi hướng item nào cho đối tượng này. Nếu thiếu thông tin → **tự soạn sẵn email tiếng Việt** hỏi requester, giải thích vì sao cần từng thông tin. |
| **Trả ra gì (output)** | Một bản phân tích ghi thẳng vào dòng project trên Airtable: phân loại, đánh giá deadline, mức ưu tiên, tóm tắt, và thư bổ sung (nếu cần). Status tự nhảy: đủ thông tin → "Chờ duyệt items", thiếu → "Thiếu thông tin". |
| **Người làm gì** | Đọc bản phân tích; nếu là case thiếu thông tin thì gửi thư cho requester (thư đã soạn sẵn). |

### Điểm AI #2 — Đề xuất bộ quà + giá dự kiến (ngay sau khi đề bài đạt)

| | Nội dung |
|---|---|
| **AI được đưa gì (input)** | (1) Đề bài đã phân tích; (2) **toàn bộ sổ giá lịch sử** — 48 dòng đơn hàng cũ: món gì, chất liệu gì, đặt bao nhiêu cái, giá bao nhiêu, năm nào, vendor nào, kèm ghi chú nghề (phí khuôn, MOQ...); (3) **hồ sơ 5 vendor**: chuyên môn, điểm đánh giá, tốc độ, lịch sử trễ hạn. |
| **AI làm gì** | Như một buyer kinh nghiệm: chọn 4-6 món hợp chủ đề/đối tượng (bắt buộc có 1 món "đinh" sáng tạo), **tra giá từ sổ — mỗi con số đều phải ghi rõ lấy từ dòng nào, cộng trượt giá ~9%/năm**, chọn vendor đúng chuyên môn và né vendor từng trễ hạn. **Quy tắc sắt: món nào không có trong sổ giá → bắt buộc ghi "chưa có dữ liệu, cần hỏi vendor"** — cấm đoán mò. |
| **Máy kiểm tra lại (không phải AI)** | Máy tự cộng tổng tiền bằng công thức. Nếu vượt budget → đưa lại cho AI kèm yêu cầu "làm lại cho vừa túi tiền" (tối đa 2 vòng). *Ví dụ thật: bộ quà Tết đề xuất lần đầu 481 triệu / budget 250 triệu → AI tự sửa: giảm figure xuống 100 con làm hàng limited cho top nạp, bù gấu bông giá mềm → chốt 245 triệu.* |
| **Trả ra gì** | Danh sách items với số lượng, giá dự kiến, vendor đề xuất, căn cứ giá — ghi thành từng dòng trong bảng Items. |
| **Người làm gì** | Approver nhận phiếu duyệt trên Zalo (đầy đủ items + tổng tiền/budget), trả lời **1 để duyệt, 2 để từ chối**. Không duyệt thì không có gì đi tiếp. |

### Điểm AI #3 — Đọc tin nhắn báo giá của vendor (khi vendor trả lời qua Zalo)

| | Nội dung |
|---|---|
| **AI được đưa gì (input)** | (1) Tin nhắn vendor viết **kiểu chat đời thường** (vd: *"áo thun 100k, 1 tuần sau giao hàng nhé ạ"*, *"figure 685k/con, phí khuôn 25tr tính riêng, cọc 50% mới lên mẫu"*); (2) danh sách items đang chờ báo giá của đơn đó. |
| **AI làm gì** | Bóc tách như một admin nhập liệu cẩn thận: "100k" = 100.000đ, "1 tuần" = thời gian sản xuất; khớp từng báo giá vào đúng món; tách điều kiện thương mại (phí khuôn, cọc) ra ghi chú riêng. **Kỷ luật quan trọng:** vendor báo món không có trong đơn → không nhét bừa (test thật: vendor báo "áo thun" trong khi đơn chỉ có "áo khoác gió" → AI không nhận nhầm); vendor nhắn nhầm đơn khác → bot lịch sự liệt kê lại đúng các món đang chờ. |
| **Trả ra gì** | Giá, MOQ, thời gian lên mẫu/sản xuất điền vào đúng từng dòng item; điều kiện phụ vào ghi chú; trạng thái item nhảy "Đã có báo giá". Khi **tất cả** items có giá → project tự nhảy "Chờ duyệt mẫu" + nhắn Zalo báo PIC. |
| **Người làm gì** | Vendor chỉ cần nhắn tin như vẫn nhắn hằng ngày — không học tool mới. PIC nhận thông báo khi đủ giá để chốt vendor. |

### Còn lại KHÔNG dùng AI — và đó là chủ đích

Gửi phiếu duyệt, ghi nhận ai duyệt lúc nào, gửi yêu cầu báo giá cho vendor, nhắc quá hạn, chuyển lên quản lý khi quá 3 ngày, đổi trạng thái, tính tổng tiền — tất cả là **chương trình chạy quy tắc cứng**, đúng 100% như máy tính bỏ túi, không có chuyện "AI tự diễn".

**Câu chốt khi sếp hỏi "tin AI được không":** *"Chỗ nào cần chắc chắn tuyệt đối (tiền, quyền duyệt, thời hạn) là code quy tắc — không phải AI. AI chỉ đứng ở 3 chỗ cần đọc-hiểu-và-tư-vấn, bị giới hạn chỉ được dùng dữ liệu nội bộ đưa cho, bị máy kiểm tra lại con số, và mọi đề xuất đều phải qua tay người duyệt mới có hiệu lực."*

---

## 4. GIỚI HẠN HIỆN TẠI (nói TRƯỚC khi bị hỏi — thể hiện hiểu sản phẩm)

| Giới hạn | Tác động | Kế hoạch |
|---|---|---|
| Phiếu chờ duyệt/RFQ lưu **in-memory** | Agent restart là mất phiên đang chờ (phải gửi lại) | Chuyển sang bảng Airtable "Pending Actions" |
| **Webhook Airtable hết hạn 7 ngày** (hiện hết hạn 18/06) | Quên refresh là form không trigger nữa | Cron refresh tự động khi deploy |
| Tunnel cloudflared tạm (URL đổi mỗi lần chạy) | Chỉ dùng dev local | Deploy AgentBase Runtime → endpoint cố định → đăng ký lại webhook |
| Webhook chỉ nghe sự kiện **tạo mới** record | "Thiếu thông tin" là ngõ cụt: requester bổ sung xong phải đổi status tay | Nghe thêm sự kiện update để tự re-analyze |
| Zalo getUpdates **consume-on-read, 1 poller duy nhất** | Chạy 2 instance agent là nuốt event của nhau | Production chuyển setWebhook |
| Chưa tự động: duyệt mẫu → nhập kho | Đang làm tiếp (cùng pattern phiếu reply 1/2) | Sprint hiện tại |
| Không tự động: PR/PO/eForm, thanh toán, branding, report | Gate pháp lý + hệ nội bộ — giữ cho người có chủ đích | Roadmap tích hợp sau |

---

## 5. BÀI HỌC KỸ THUẬT ĐẮT GIÁ (kể khi sếp kỹ thuật hỏi sâu)

1. **Zalo Bot Platform KHÔNG có nút bấm** — docs chỉ có 8 method (sendMessage/Photo/Sticker/ChatAction + getUpdates/webhook); gửi `reply_markup` trả `ok:true` nhưng lặng lẽ bỏ qua (false positive). Giải pháp: phiếu duyệt reply-lệnh "1/2" — danh tính vẫn verified, UX chấp nhận được, demo câu chuyện "không cần cài gì".
2. **Bot không vào được group Zalo** (dù getMe khai can_join_groups) → mọi flow thiết kế quanh chat 1-1; phê duyệt bản chất là việc cá nhân nên không sao.
3. **getUpdates consume-on-read** — 2 process cùng poll thì tranh nhau nuốt event (mất 1 buổi debug). Quy tắc: agent là consumer DUY NHẤT.
4. **Qwen thinking mode** mặc định bật → đốt hết max_tokens vào reasoning, content rỗng. Tắt bằng `chat_template_kwargs`.
5. **Không tin số model tự cộng** — tổng tiền proposal tính lại bằng Python; vượt budget thì ép model sửa (tối đa 2 vòng). Đây là pattern "code kiểm tra, LLM sáng tạo".
6. **Test giả lập ≠ test thật** — 6 phiên test giả lập sạch sẽ không lộ 3 bug mà 1 lần submit form thật lộ ra ngay (status trống, mã trống, vô chủ).

---

## 6. FAQ — DỰ ĐOÁN CÂU HỎI CỦA SẾP

**Q: "Agent" là gì? (hỏi kiểu không làm tech)**
A: Agent là một **nhân viên số trực 24/7** — một chương trình chạy liên tục trên cloud của VNG, khác chatbot ở chỗ: chatbot phải có người hỏi mới trả lời, còn agent **tự canh việc và tự làm việc**. Agent của ta trực 3 "cửa" cùng lúc: (1) cửa Airtable — có đơn mới là bắt tay xử lý ngay; (2) cửa Zalo — có tin duyệt/báo giá đến là ghi nhận ngay; (3) đồng hồ — cứ vài tiếng rà một lượt xem có gì quá hạn để đi nhắc. Khi cần "suy nghĩ" (đọc đề bài, tra giá, đọc tin vendor) nó gọi bộ não AI thuê theo cuộc gọi của GreenNode; khi cần làm việc chắc chắn (gửi tin, đổi trạng thái, tính tiền, nhắc hạn) nó dùng quy tắc cứng. Nó không bao giờ nghỉ, không quên việc, và không tự quyết — đến điểm cần quyết định là dừng lại chờ người.

**Q: Hiện tại quy trình vận hành thế nào? (so với trước)**
A: Kể theo vai — mỗi người giờ chỉ còn đúng phần việc của mình:
- **Requester (game studio):** điền 1 form ~2 phút. Hết việc. Thiếu thông tin thì nhận được thư hỏi lại rõ ràng cần gì, vì sao.
- **Agent (tự động, ~2-3 phút sau khi form gửi):** phân tích đề bài → kiểm tra deadline có kịp sản xuất không → lên bộ quà đề xuất kèm giá dự kiến tra từ sổ giá lịch sử → tự điều chỉnh cho vừa budget → gửi phiếu duyệt vào Zalo người duyệt.
- **Approver:** nhận tin Zalo, đọc phiếu (items + tổng tiền/budget), nhắn **1** (duyệt) hoặc **2** (từ chối). Quên thì 6 tiếng bị nhắc một lần, quá 3 ngày thì quản lý của họ nhận tin escalate.
- **Agent (ngay khi duyệt):** tự gửi yêu cầu báo giá đến từng vendor đúng chuyên môn, kèm spec đầy đủ (chất liệu, kích thước, số lượng, deadline).
- **Vendor:** nhắn giá qua Zalo **như vẫn chat hằng ngày** — không cần học tool nào. Agent tự bóc số liệu điền vào hệ thống.
- **Merch PIC:** nhìn dashboard Airtable thấy mọi đơn đang ở bước nào; nhận thông báo khi đơn đủ báo giá để chốt vendor; chỉ phải nhúng tay vào ngoại lệ (form vô chủ, vendor từ chối, deadline không kịp).
So với trước: PIC từng phải tự nhận đề bài, tự phân tích, tự nhớ giá cũ, tự soạn proposal, tự nhắn từng vendor, tự chép giá vào sheet, tự nhớ deadline đi đòi duyệt — **toàn bộ phần "tay chân + trí nhớ" đó giờ tự chạy**, PIC chỉ còn ra quyết định. Một đơn từ lúc gửi form đến lúc có phiếu duyệt trên điện thoại: dưới 3 phút thay vì 1-2 ngày chờ xử lý tay.

**Q: Các khái niệm LLM / tool / MCP / skill có trong hệ thống này không? Là gì?**
A: Chia 2 thời điểm:
- **Trong sản phẩm đang chạy:** (1) **LLM** = bộ não — mô hình Qwen 3.5 27B thuê trên GreenNode (VNG Cloud), được gọi đúng 3 chỗ cần đọc-hiểu (đề bài, đề xuất quà+giá, tin báo giá vendor); mỗi lần gọi như một cuộc điện thoại hỏi chuyên gia kèm tài liệu. (2) **Tool** = tay chân (ghi Airtable, nhắn Zalo, nhắc hẹn) — nhưng **code quy tắc cầm tool, không phải AI cầm**: LLM chỉ tư vấn nội dung, mọi hành động ra ngoài đều do chương trình chắc chắn 100% thực hiện. Đây là lựa chọn an toàn có chủ đích (nhiều hệ thống cho AI tự gọi tool — ta không, để dễ kiểm soát). (3) **MCP và skill: KHÔNG có trong sản phẩm chạy.**
- **Trong quá trình XÂY sản phẩm:** MCP và skill là lý do xây nhanh. **MCP** (chuẩn kết nối AI với hệ thống ngoài — như "cổng USB-C của giới AI"): trợ lý AI lập trình đã cắm Airtable MCP chính thức để tự dựng 5 bảng + 73 dòng data mẫu + kiểm tra test. **Skill** (sổ tay nghề đóng gói cho AI lập trình): bộ skill GreenNode AgentBase do chính VNG Cloud phát hành đã hướng dẫn AI tự scaffold project, lấy API key LLM, deploy runtime.
- **Câu chốt:** "LLM là bộ não đi thuê của sản phẩm; tool là tay chân nhưng code cầm chứ không để AI tự cầm; MCP và skill là đồ nghề giúp xây sản phẩm trong 1 ngày thay vì 1 tháng."

**Q: Cái này khác gì Airtable Automations có sẵn?**
A: Automations chỉ làm if-this-then-that (gửi mail template khi status đổi). Phần giá trị ở đây là tầng AI: đọc hiểu đề bài tiếng Việt tự do, tra giá lịch sử có căn cứ, tự đề xuất trong budget, parse tin nhắn vendor viết tay. Automations không làm được bất kỳ cái nào trong số đó. Ta vẫn dùng webhook native của Airtable cho phần trigger — đúng việc đúng tool.

**Q: AI bịa giá thì ai chịu trách nhiệm?**
A: 3 tầng phòng thủ: (1) giá CHỈ được tra từ Price History thật, item không có data → AI bắt buộc trả "chưa có giá, cần hỏi vendor" — đã test; (2) tổng tiền do code tính, không phải model; (3) MỌI con số đều qua phiếu duyệt của người trước khi đi tiếp — AI đề xuất, người quyết.

**Q: Sao không làm trên Teams/mail cho chính thống?**
A: Vendor sản xuất VN không dùng Teams, và thực tế chốt giá qua Zalo hằng ngày. Mail + Teams nằm ở roadmap (kiến trúc adapter — logic không đổi, thêm kênh là thêm adapter). Telegram bị loại vì đang trong diện chặn tại VN.

**Q: Fresh staff dùng cái này thế nào? (đúng pain point đề bài)**
A: Kiến thức 5-10 năm kinh nghiệm (giá nào hợp lý, chất liệu gì, MOQ bao nhiêu, vendor nào tốt, lead time bao lâu) giờ nằm trong Price History + Vendors + prompt nghiệp vụ. Fresh chỉ cần đánh giá đề xuất của agent thay vì tự nghĩ từ số 0. Mỗi đơn hoàn thành lại làm giàu thêm Price History — hệ thống tự tốt lên.

**Q: Chi phí vận hành?**
A: LLM: Qwen 3.5 27B free trên GreenNode (model trả phí chỉ khi cần nâng chất lượng). Airtable Team ~$24/user/tháng. Zalo Bot free. AgentBase Runtime theo flavor. Tổng cỡ vài trăm nghìn đến ~1tr/tháng — so với chi phí 1 headcount quản lý thủ công.

**Q: Bảo mật? Token để đâu?**
A: Secrets trong .env/.greennode.json (gitignore), Airtable PAT giới hạn đúng 1 base + 3 scope, danh tính phê duyệt verified bởi Zalo platform (không giả mạo được user_id), audit log đầy đủ ai-duyệt-lúc-nào trên record.

**Q: Scale nhiều game/nhiều PIC thì sao?**
A: Approval matrix là DATA (bảng Users: ai duyệt, manager là ai) — thêm người là thêm record. Nhiều project song song đã chạy được (PENDING theo chat_id). Điểm cần nâng khi scale thật: pending state sang Airtable, Zalo chuyển webhook, tách worker.

**Q: Mất bao lâu để xây? Bao nhiêu người?**
A: MVP golden path: ~1 ngày làm việc với AI pair-programming (kế hoạch dự phòng 7 ngày), 1 người + Claude. Codebase ~750 dòng Python, không framework nặng.

### 6.1 Demo & độ thật

**Q: Demo cho tôi xem luôn được không?**
A: Được — demo live theo kịch bản 3 phút: (1) mở form Airtable, điền đề bài merch mới ngay trước mặt sếp; (2) chờ ~1-2 phút, điện thoại rung — phiếu duyệt Zalo hiện items + giá + tổng tiền/budget; (3) reply "1" → agent tự gửi yêu cầu báo giá cho vendor (màn hình thứ hai đóng vai vendor); (4) vendor nhắn "áo thun 100k, 1 tuần giao" kiểu chat thường → bảng Items trên Airtable tự điền giá. *Chuẩn bị trước buổi present: agent + tunnel đã bật, webhook còn hạn, và LUÔN có video quay sẵn toàn trình làm phương án B (mạng/Zalo trục trặc là chuyện không kiểm soát được).*

**Q: Số liệu giá trong demo là thật hay anh tự bịa?**
A: Data mẫu — dựng có chủ đích để mô phỏng đúng cấu trúc sổ giá thật: có price break theo số lượng, giá thay đổi theo năm, đa chất liệu, và cố tình để 1 món không có giá để chứng minh AI không bịa. Khi triển khai thật chỉ cần nhập sổ giá thật của team merch vào — **hệ thống không phải sửa một dòng code nào**, vì AI chỉ tra cứu chứ không học thuộc data.

**Q: Quy trình gốc 17 bước mà mới tự động được mấy bước — vậy mới làm được 1/3?**
A: Đếm theo bước thì vậy, nhưng đếm theo **độ nặng** thì khác: đoạn intake → phân tích → proposal → duyệt → báo giá là đoạn tốn chất xám và thời gian chờ nhất (đòi hỏi kiến thức giá/chất liệu/vendor mà fresh không có). Các bước còn lại chia 2 loại: (a) duyệt mẫu → sản xuất → nhập kho — **đang làm tiếp ngay sprint này**, dùng lại đúng pattern phiếu Zalo đã chạy; (b) PR/PO/eForm/thanh toán — **cố tình giữ cho người** vì là gate pháp lý và dính hệ nội bộ, tự động hóa phần này là roadmap tích hợp sau khi có API.

### 6.2 Rủi ro & vận hành

**Q: Người duyệt bấm nhầm "1" thì sao? Hủy được không?**
A: Hiện chưa có lệnh "hủy" trong chat — nhưng có lưới an toàn: duyệt xong agent mới chỉ *gửi yêu cầu báo giá*, chưa có cam kết tiền nong nào với vendor. Phát hiện nhầm thì PIC đổi status trên Airtable là dòng chảy dừng lại, nhắn lại vendor một câu là xong. Roadmap: thêm lệnh hủy trong vòng X phút + bước xác nhận lại cho đơn vượt ngưỡng tiền.

**Q: Hệ thống sập / Zalo trục trặc thì cả quy trình tắc luôn à?**
A: Không — đây là điểm thiết kế quan trọng: **Airtable luôn là nguồn sự thật, và con người đọc được toàn bộ**. Agent chết thì không mất dữ liệu nào, mọi đơn vẫn nằm đó với status rõ ràng — team quay về xử lý tay trên chính data đó như trước khi có agent, rồi agent sống lại thì tiếp tục. Tệ nhất là chậm, không bao giờ là mất.

**Q: Dữ liệu budget, giá vendor gửi cho AI — có lộ ra ngoài không? Qwen là model Trung Quốc mà?**
A: Qwen là model **mã nguồn mở**, nhưng quan trọng là nó chạy ở đâu: ta thuê bản chạy trên **GreenNode — hạ tầng VNG Cloud, server tại Việt Nam**. Dữ liệu đi từ Airtable đến LLM đều trong phạm vi dịch vụ VNG, không gửi cho Alibaba hay bất kỳ bên thứ ba nào, không dùng để train model. So với việc nhân viên hiện tại vẫn dán data vào ChatGPT công khai để nhờ soạn mail — đây là bước **tăng** kiểm soát chứ không phải thêm rủi ro.

**Q: Sổ giá sai thì AI tư vấn sai đúng không?**
A: Đúng — AI chỉ tốt bằng dữ liệu được đưa (nguyên tắc garbage in, garbage out). Vì thế thiết kế bắt buộc: mỗi con số đề xuất đều **ghi rõ căn cứ từ dòng nào trong sổ** — người duyệt truy được tận gốc, thấy sai thì sửa sổ một lần là mọi đề xuất sau đúng theo. Và mỗi đơn hoàn thành lại tự bồi thêm giá mới vào sổ — dữ liệu tự tốt lên theo thời gian, không thoái hóa.

### 6.3 Con người & tổ chức

**Q: Vậy team merch có giảm người không?**
A: Không thay người — thay **phần việc không ai muốn làm**: chép số liệu, nhớ giá cũ, nhắn từng vendor, đi đòi duyệt. PIC chuyển từ "tay chân + trí nhớ" sang đúng việc của con người: ra quyết định, đàm phán, giữ quan hệ vendor. Giá trị lớn nhất nằm ở chỗ khác: mùa cao điểm **không cần tuyển thời vụ gấp**, và fresh staff vào việc được ngay tuần đầu thay vì mất 6 tháng học giá học vendor — đúng pain point của đề bài.

**Q: Vendor có chịu nhắn tin với bot không? Họ có biết đang nói chuyện với máy không?**
A: Phía vendor **không phải thay đổi bất cứ gì**: không cài app, không học tool, không format tin nhắn — nhắn Zalo như vẫn nhắn hằng ngày, kiểu "685k/con, phí khuôn tính riêng" là hệ thống hiểu. Trải nghiệm của họ thực ra tốt lên: yêu cầu báo giá đến với spec đầy đủ rõ ràng (chất liệu, số lượng, deadline), và được phản hồi nhanh. Về minh bạch: tin nhắn đến từ tài khoản bot có tên rõ ràng, không giả dạng người.

**Q: Reply "1" trên Zalo có giá trị kiểm toán/pháp lý không?**
A: Tách 2 tầng: tầng **kiểm toán nội bộ** — có: danh tính người duyệt do nền tảng Zalo xác thực (user_id không giả mạo được), hệ thống ghi log "DUYỆT bởi ai, lúc nào, qua kênh nào" vào thẳng record. Tầng **pháp lý/tài chính** — phê duyệt Zalo chỉ là gate *nghiệp vụ* để đi tiếp; chứng từ chính thức (PR/PO/eForm, thanh toán) vẫn đi đường hệ thống chính thống có chữ ký — và đó chính là lý do ta **cố tình không** tự động hóa đoạn đó.

### 6.4 Tương lai

**Q: Bao giờ dùng thật được? Cần gì để pilot?**
A: 3 việc, cỡ 1-2 tuần: (1) deploy lên AgentBase Runtime để có địa chỉ cố định chạy 24/7 (đường deploy đã sẵn, đây là output hackathon); (2) nhập sổ giá thật + danh sách vendor thật của team merch; (3) chọn 1 team game pilot trọn 1 mùa merch. Sau mùa đó có con số thật — số đơn, thời gian xử lý, lỗi — để quyết định scale toàn bộ hay chỉnh tiếp.

**Q: Sao không mua tool có sẵn ngoài thị trường?**
A: Vì không tồn tại tool nào khớp bài toán này: phần mềm procurement quốc tế không có Zalo, không hiểu tin nhắn vendor tiếng Việt, và quan trọng nhất — **phần lõi giá trị là sổ giá lịch sử + quy tắc nghiệp vụ của chính VNGGames**, thứ không hãng nào bán. Phần "vỏ" (form, database, chat) ta dùng đồ có sẵn hết (Airtable, Zalo, GreenNode) — chỉ tự viết đúng phần ghép nối + nghiệp vụ, ~750 dòng code, 1 người + AI làm trong ngày.

### 6.5 Câu hỏi thử phản xạ

**Q: Nói trong 1 câu — cái này giúp gì cho tôi?**
A: *"Một đơn merch từ lúc điền form đến lúc có phiếu duyệt kèm giá trên điện thoại mất chưa đến 3 phút thay vì 1-2 ngày — và fresh staff làm được việc trước đây cần người 5 năm kinh nghiệm."*

**Q: Nếu tôi cho thêm 1 tháng và 1 người nữa, anh làm gì tiếp?**
A: Theo thứ tự giá trị: (1) deploy production + khép nốt vòng đời duyệt mẫu → nhập kho (đang làm); (2) chuyển pending state vào Airtable để agent restart không mất phiên; (3) mail adapter cho vendor lớn cần audit trail + Teams cho khối văn phòng; (4) báo cáo tháng/quý tự sinh từ data — phần này gần như free vì data đã nằm sẵn trong Airtable đúng cấu trúc.

**Q: Điều gì khiến anh LO NHẤT nếu đưa vào dùng thật?**
A: Hai điều, nói thẳng: (1) **phiếu chờ duyệt đang lưu trong bộ nhớ** — agent restart là mất phiên đang chờ, phải gửi lại phiếu; đã có giải pháp (chuyển vào bảng Airtable) nhưng chưa làm. (2) **Phụ thuộc Zalo Bot Platform** — nền tảng còn mới, ít tính năng (không nút bấm, không group); đã thiết kế dạng adapter nên nếu Zalo thay đổi, swap kênh khác không phải đập logic. Cả hai đều là rủi ro biết trước có kế hoạch, không phải rủi ro ẩn.

---

## 7. ROADMAP (slide cuối)

- **Sprint này:** duyệt mẫu qua Zalo (vendor báo mẫu → phiếu duyệt mẫu, đếm round) → confirm sản xuất → remind giao hàng (trước 2 ngày) → xác nhận nhập kho → Hoàn tất. Deploy AgentBase Runtime + webhook cố định. Commit/tag mốc.
- **Production hóa:** pending state vào Airtable; webhook update-event (hết ngõ cụt "Thiếu thông tin"); mail adapter (Outlook/Graph, shared mailbox, match [MERCH-x]); Teams adapter cho khối văn phòng; group Zalo khi platform mở bot-in-group.
- **Mở rộng nghiệp vụ:** tích hợp eForm/PR/PO khi có API nội bộ; báo cáo tháng/quý tự sinh từ data Airtable; vendor scorecard tự cập nhật (đúng hạn, số round sửa mẫu); knowledge base vật liệu từ Win-Lose log (bước 17 quy trình gốc).
