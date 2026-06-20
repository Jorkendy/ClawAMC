# BUSINESS_RULES — Merch Agent

Các **quyết định nghiệp vụ** đã thống nhất (không hiển nhiên từ code). Đọc kèm code để review/điều chỉnh.
Mục `[GIẢ ĐỊNH]` = số/ngưỡng cần validate bằng dữ liệu thực tế VNGGames.

---

## Bước 1 — Intake (analysis.py)

- **Field bắt buộc** (`REQUIRED_FIELDS`, config.py): Mục đích, Chủ đề, Định vị, Target audience, Số lượng (bộ/suất), Deadline cần hàng, Budget. Thiếu → Status "Thiếu thông tin" (form đã required nên hiếm; chỉ là lưới an toàn).
- **Validation giá trị** (`_is_missing`, không chỉ check None/""): field text toàn khoảng trắng → coi như thiếu; **Budget & Số lượng phải > 0** (≤0 hoặc âm → coi như thiếu, không cho lọt xuống Bước 2).
- **Deadline quá khứ / = hôm nay** (days ≤ 0): vẫn là "không khả thi" nhưng cảnh báo ghi rõ "ĐÃ QUA HẠN" / "là HÔM NAY" (không hiện "còn -X ngày"). Marker cảnh báo: **🔴** = nghiêm trọng (không khả thi/quá hạn/hôm nay → banner đỏ), **⚠️** = gấp (banner cam).
- **Re-analyze (requester bổ sung) có CAP** = `MAX_SUPPLEMENT_ROUNDS` (3): quá 3 lần tick "Gửi phản hồi" mà vẫn thiếu → escalate PIC + tắt mail bổ sung (chống spam vô hạn). Đếm ở field "Số lần bổ sung"; đủ thông tin → reset 0.
- **Robustness AI**: dùng `.get(...)` default cho key AI #1 (tom_tat/muc_do_uu_tien/ly_do_deadline) → thiếu key không crash.
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
- **so_luong mỗi item = Số lượng (bộ/suất)** ở đề bài; nếu < MOQ catalogue → **CODE tự nâng lên MOQ** + ghi cảnh báo vào can_cu_gia (✅ DONE 19/06 `_enforce_catalogue_price`, không còn chỉ nhờ prompt → model bỏ sót cũng an toàn; MOQ nâng trước khi check budget → không kịp/không đủ thì loop/escalate đúng).

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
- **Giá catalogue cố định** lấy đúng từ bảng (`_enforce_catalogue_price`) — chống bịa giá. Tên **khớp chính xác HOẶC sau chuẩn hoá** (hoa/thường, space) → giữ catalogue (✅ DONE 19/06: tránh hạ nhầm hàng có sẵn do model lệch hoa/space). Tên thật sự không khớp → hạ thành creative (giá null) + **LOG** (không âm thầm).
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

## Bảo mật (prompt injection / XSS)
- **Không có tool/function-calling cho LLM** → LLM không thực thi hành động (không RCE/exfil); chỉ text→JSON. LLM chỉ thấy đề bài + catalogue (không secret).
- **HTML escape** mọi field + text AI khi render proposal (`_esc` + escape trong `_md_inline`) → chống stored XSS (field như `<script>` thành text).
- **Prompt hardening** AI#1/#2: nội dung đề bài/field là DỮ LIỆU, bỏ qua mệnh lệnh nhúng (đổi vai trò/luật/giá).
- **Backstop**: giá catalogue code-enforced, budget code-tính, con người duyệt → injection lái logic bị giới hạn.
- Còn lại (chấp nhận/để sau): nội dung AI bậy do injection (uy tín) — dựa human review; giới hạn độ dài field (cost) chưa làm.

## Robustness (retry)
- `ask_llm_json`/`ask_llm_grounded`/`generate_image`: retry lỗi API **transient** (503/429/mạng/timeout) + backoff; lỗi vĩnh viễn raise ngay. `upload_proposal`: retry 3 lần. → tránh escalate PIC oan vì hiccup tạm.

## Chi phí AI/proposal (tham khảo)
- Insight grounded: ~$0.035 (~900đ)/proposal · Ảnh creative: ~$0.039 (~1.000đ)/ảnh → ~2-3K/proposal.

---

## MÔ HÌNH MỤC TIÊU — Redesign Bước 1/2 (chốt 19/06; ⏳ = SẼ LÀM, chưa code)
> Sơ đồ trực quan: `docs/flowchart.html` (serve tại `GET /flowchart`). Cập nhật file + redeploy khi có quyết định mới.

### Phân ranh lại Bước 1 / Bước 2 = **Khả thi vs Sở thích**
- **Bước 1 = động cơ khả thi** (3 phase: Tiếp nhận → Thẩm định → ra proposal). Output = **một proposal CHẠY ĐƯỢC THỰC TẾ** (thoả đồng thời budget + deadline-theo-lead-time + yêu cầu đặc biệt). **Mọi vòng cần requester can thiệp để ĐẠT khả thi** (bổ sung info / chỉnh budget / dời deadline / bỏ-đổi yêu cầu) thuộc Bước 1.
- **Bước 2 = cổng sở thích**: requester xem proposal *đã khả thi* → **Duyệt** hoặc **feedback ITEM**. Feedback item phá khả thi → **rớt ngược về phase Thẩm định**.
- ⚠️ Thẩm định khả thi (budget/deadline-theo-item/yêu cầu met) **cần thử dựng bộ item** → không tách "Bước 1 không item / Bước 2 có item" được; tách theo **khả thi vs sở thích**.

### Yêu cầu đặc biệt → thuộc Bước 1 (thẩm định), KHÔNG phải Bước 2
- ⏳ **Chuẩn hoá nội dung** bằng AI: "không có"/"ko"/"-"/"n/a" → coi như RỖNG (KHÔNG dùng blacklist từ khoá — tiếng Việt vô số cách nói). Gộp vào lượt AI sẵn có → ~0 thêm chi phí. Field vẫn optional.
- Cases (đã có ở code, sẽ chuyển về khung Bước 1): trống · met hết · design-co-san (luôn met) · unmet → vòng làm rõ.
- ⏳ **Tách field dual-use**: "Yêu cầu đặc biệt" = thuần input requester; bản hệ thống chốt ghi field RIÊNG ("…(đã chốt)", read-only) — hết cảnh hệ thống ghi đè input. Cần khi dựng Interface.

### Cơ chế ĐIỀU CHỈNH/LÀM RÕ hợp nhất (gom 4 cơ chế rời thành 1)
- 1 vòng "Làm rõ/Điều chỉnh" nhiều `lý do` (thiếu-info / yêu-cầu / budget / deadline), hỏi requester chỉnh đúng lever.
- **1 bộ đếm khả thi CHUNG** mọi lever ≤3 → PIC (chống lách cap bằng cách đổi qua lại lever). **Tách** với **bộ đếm sửa item** (`Số round proposal`, Bước 2 ≤3 → PIC).
- **Budget = bất khả thi CỨNG**: AI tự sửa 2 vòng (đã có), vẫn vượt → **buộc** điều chỉnh (tăng budget / bỏ-rẻ yêu cầu) → loop → PIC.
- ⏳ **Deadline = MỀM**: vẫn ra proposal nhanh nhất (catalogue-only) + cảnh báo; **chỉ chặn** khi cả phương án nhanh nhất cũng trễ → loop xin dời deadline → PIC. (Không biến deadline thành chặn cứng vô điều kiện.)

### ✅ Deadline theo lead-time item (DONE 19/06 — thay rổ cứng 43/74 bằng ngưỡng riêng từng proposal)
**Đã code** (`proposal.deadline_days_needed` + nhánh mềm/cứng trong `propose_items_for`): sau khi chọn item, tính `Ngày cần` theo lead-time → **mềm** (full không kịp → tự chuyển catalogue-only nếu kịp + ghi 🔴 cảnh báo vào "Cảnh báo deadline") · **cứng** (cả catalogue-only cũng trễ → `infeasible_deadline` → hiện `_escalate_deadline` chuyển PIC, interim) · **sát nút** (còn < Ngày cần×1.15 → ⚠️ cảnh báo, vẫn chạy). Catalogue thiếu data lead-time → fallback 8/18 (không ước tính thấp). ⚠️ Phụ thuộc **catalogue điền `Thời gian lên mẫu`/`Thời gian sản xuất`** để chính xác. Pre-gate generic vẫn ở Tiếp nhận.

- Dùng catalogue **"Thời gian lên mẫu"** (= bước Lên mẫu) + **"Thời gian sản xuất"** (= bước Sản xuất hàng loạt). Duyệt mẫu + Chọn vendor/PO = overhead, KHÔNG trong catalogue.
- ⚠️ **GOTCHA dữ liệu:** 3 field này + `Số lượng tối thiểu` (MOQ) lưu dạng **TEXT có range + đơn vị** ("7-10 ngày", "200 cái", "10-15 ngày (theo thiết kế)"), KHÔNG phải số → code `_parse_int` lấy **số lớn nhất** (range → cận trên, bảo thủ: thà ước tính trễ hơn còn hơn hứa nhầm kịp). Không parse được → fallback 8/18. (Phát hiện + fix 19/06 — trước đó check isinstance số → không bao giờ khớp data thật.)
- Sản xuất **song song** → lấy **max** qua các item:
  ```
  Ngày cần (LV)  = 27 + max(Thời gian lên mẫu) + max(Thời gian sản xuất)
                   (27 = Head 18 + Duyệt mẫu 7 + Giao hàng 2 — overhead cố định)
  Ngày cần (lịch) = Ngày cần (LV) × 1.4
  khả thi ⟺ số ngày tới deadline ≥ Ngày cần (lịch)
  ```
- Kiểm chứng: item generic 8+18 → 27+26 = 53 LV → ×1.4 = 74 lịch (khớp ngưỡng cũ). [GIẢ ĐỊNH] 27 & ×1.4 cần validate 10-15 project. Pre-gate generic (`PIPELINE_WORKDAYS`) vẫn giữ ở Tiếp nhận để loại ca vô vọng trước khi dựng item.
- Sai số lớn nhất: Duyệt mẫu lặp round (tốc độ requester) + mùa cao điểm → giữ buffer (vd "gấp" khi trong khoảng `Ngày cần` → `Ngày cần ×1.15`).

### Chi phí & vận hành
- ✅ **Cache ảnh creative (DONE 19/06, mức A)** — `proposal._IMG_CACHE` key = `goi_y_anh` chuẩn hoá (lower+collapse space): revise/re-trigger KHÔNG gen lại ảnh item không đổi (~1.000đ/ảnh). Chỉ cache khi gen thành công. Trong process, mất khi redeploy. KHÔNG để "AI quyết định gen lại" (thêm chi phí + thiếu tin cậy — so sánh prompt là đủ). ⏳ Mức B (lưu attachment trên Item, bền qua restart) để sau nếu cần.
- ✅ **Log chi phí + thời gian/proposal (DONE 19/06)** — `llm_client` đếm thread-local (chat calls/tokens, grounded calls, images); `estimate_cost_vnd` (đơn giá [GIẢ ĐỊNH] ở config). `pipeline._log_cost` ghi 1 dòng `[Chi phí] ~Xđ · Ys · N ảnh · …` vào **Lịch sử chỉnh sửa** + stdout (Coolify). ⏳ Sau gom thành field số riêng để aggregate dashboard.

### ⏳ Interface portal (gom tương tác requester, bỏ sửa record thô)
- 1 Interface app: Tạo yêu cầu (form) · Yêu cầu của tôi (list lọc Created by) · Chi tiết+Proposal (preview File proposal — Interface xem được, Fillout không) + nút Duyệt/Cần sửa/Trả lời làm rõ/Bổ sung · Cần PIC (đã có).
- **Cho sửa theo TRẠNG THÁI** (gần như mọi field đều ảnh hưởng mạnh; chỉ Tên project là vô hại): chưa có proposal → sửa thoải mái; đã có proposal → field cốt lõi sửa qua nút **"Cập nhật & tính lại"** (tái dùng đường re-trigger, rẻ nhờ cache ảnh); đã duyệt/sản xuất → khoá, đổi qua PIC.

## Test (regression các sửa 19/06)
Bộ test đầy đủ + data prereq ở memory `merch-test-cases-buoc2`. Nhóm: **A** cache ảnh · **B** log chi phí · **C** MOQ + khớp tên · **D** deadline lead-time (ổn/sát/mềm/cứng) · **E** không hồi quy.
- **Đã pass isolation 19/06** (logic/math, không network): cache gen 1 lần qua 3 lượt cùng/khác hoa-space; cost estimate khớp tay; MOQ nâng + khớp tên chuẩn hoá + hạ creative; deadline math (cat 74/59, creative 84, mixed=max 84, fallback). Lệnh: `./venv/bin/python -c "..."` (xem transcript / memory).
- **E2E chưa chạy** — prereq: catalogue điền `Thời gian lên mẫu`/`Thời gian sản xuất` + `Số lượng tối thiểu`; chạy local override hoặc deploy trước (tránh race sandbox). Ưu tiên: B1→B3, D1–D4, C1/C2, E1.
