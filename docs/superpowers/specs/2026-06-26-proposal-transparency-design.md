# Spec — Trang `/proposal` (minh bạch cách tạo proposal)

**Ngày:** 2026-06-26 · **Trạng thái:** Design (chờ duyệt) · **Loại:** trang tài liệu HTML tĩnh (như `/guide`, `/rules`).

## 1. Mục tiêu & lý do

Trong dữ liệu hiện tại, requester (và cả PO) thường hỏi:
- *"Tại sao tới ~84 ngày, lâu vậy?"*
- *"Items này được suggest từ đâu?"*

Và agent **gần như luôn báo "không kịp deadline"** — vì overhead + lead-time cộng lại lớn (xem §4). Trang `/proposal` là **công cụ giải trình minh bạch** trả lời đúng các câu hỏi đó, đủ rõ cho **non-tech + leader**, và **phơi bày con số nào chắc chắn (✅) / con số nào là ước tính bảo thủ (🟡)** để cả team có cơ sở góp ý / hiệu chỉnh.

**Phạm vi:** CHỈ xoay quanh *cách một proposal được tạo ra* (timeline, chọn item, giá, ngân sách, yêu cầu đặc biệt). **KHÔNG** đưa vòng duyệt / điều chỉnh / escalate PIC / hạn duyệt (đó là vận hành, để ở `/rules`/`/guide`).

**Không trong phạm vi:** trang này **làm minh bạch** số liệu, **KHÔNG hiệu chỉnh** công thức. Việc recalibrate (overhead 27, ×1.4, creative 8/25) là task riêng, cần validate bằng 10–15 dự án thật (đã trong backlog).

## 2. Quan hệ với `/rules`

`/rules` (proposal-rules.html) hiện cover cùng chủ đề nhưng nông, không ví dụ, không truy nguồn số, và **chứa số stale** ("bộ làm mới ~136 ngày / hàng có sẵn ~56 ngày" — KHÔNG khớp công thức code thật, xem §4).

**Quyết định:** xây `/proposal` **bao hàm toàn bộ nội dung proposal của `/rules`** + sâu hơn (ví dụ + truy nguồn + Gantt). Giữ `/rules` tạm thời; **xoá `/rules` ở bước sau** khi user xác nhận `/proposal` đã đủ (việc xoá = bỏ route + xoá khỏi `_DOC_NAV_ITEMS` + xoá file + cập nhật test, làm sau, KHÔNG trong spec này).

## 3. Văn phong & quy tắc nội dung (áp đúng `/guide`)

- Người đọc: requester non-tech + leader. Viết bằng lời, ưu tiên trực quan.
- KHÔNG lộ chi tiết kỹ thuật: tên env var, tên/ID field Airtable, mã email nội bộ, tên hàm code.
- Giữ thuật ngữ tiếng Anh: **Requester / Agent / Merch PIC** (không dịch).
- Giọng trung lập theo vai — KHÔNG xưng "bạn/tôi" (test FORBIDDEN chặn `bạn`/`Bạn`).
- **Mọi con số ngưỡng/giả định chèn từ config lúc serve** qua placeholder `{{...}}` (xem §9) → số trên trang KHÔNG bao giờ lệch hệ thống thật.
- Nhãn độ tin cậy bằng ngôn ngữ thường:
  - ✅ **Số thật** — lấy từ kho hàng hoặc từ đề bài requester (chính xác).
  - 🟡 **Ước tính** — giả định nội bộ, cần kiểm chứng (có thể sai lệch).

## 4. Nội dung lõi — công thức deadline (THẬT, từ code)

> Tất cả số dưới đây lấy từ `config.py` + `proposal.py` (KHÔNG dùng số stale của `/rules`).

**Công thức nhu cầu thời gian** (`deadline_days_needed`, sản xuất song song → lấy max qua các item):

```
Ngày cần (LV)   = OVERHEAD(27) + max(Thời gian lên mẫu) + max(Thời gian sản xuất)
Ngày cần (lịch) = Ngày cần (LV) × 1.4   (làm tròn)
OVERHEAD 27 LV  = Chuẩn bị/Head 18 + Duyệt mẫu 7 + Giao hàng 2
```

**Lead-time mỗi item** (`item_leadtime`):
- **Catalogue**: lấy từ field "Thời gian lên mẫu"/"Thời gian sản xuất" của kho; **thiếu/không parse được → fallback 8/18 LV** (bảo thủ, không ước tính thấp).
- **Creative** (chưa có trong kho): hằng số giả định **8 (lên mẫu) / 25 (sản xuất)** — lâu hơn vì phải thiết kế.

**Hai mốc đối chiếu (số THẬT từ công thức, thay số stale 136/56 của `/rules`):**
| Bộ | LV | Lịch (×1.4) |
|---|---|---|
| Toàn hàng có sẵn (generic 8/18) | 27+8+18 = 53 | **74 ngày** |
| Có item creative (8/25) | 27+8+25 = 60 | **84 ngày** ← chính là "84 ngày" user hỏi |

**Sàn tuyệt đối** (`catalogue_floor_days`): món catalogue NHANH NHẤT → mốc trung thực khi báo không kịp. Nếu kho **chưa điền** lead-time → mỗi món fallback 8/18 → **sàn = 74 ngày**.

**👉 Vì sao "gần như luôn báo không kịp" (insight then chốt cho user):** chỉ riêng OVERHEAD 27 LV × 1.4 ≈ **38 ngày lịch** trước khi tính bất kỳ item nào; cộng lead-time → 74–84 ngày. Phần lớn request gửi tới với < 74 ngày → tự động không kịp. Trang phải nói rõ điều này + chỉ ra: muốn rút ngắn phải (a) điền lead-time thật ngắn hơn cho kho, hoặc (b) hiệu chỉnh overhead/hệ số (task riêng).

**3 kết cục deadline** (`_resolve_deadline`, deterministic — đối chiếu `còn lại` = ngày lịch tới deadline):
| Kết cục | Điều kiện (code) | Agent làm gì |
|---|---|---|
| ✅ **ĐỦ** (`ok`) | `ngày cần ≤ còn lại` | Ra bộ đầy đủ. Nếu `còn lại < ngày cần × 1.15` → kèm cảnh báo "sát nút", vẫn chạy. |
| ⚠️ **GẤP → phương án nhanh** (`fast`) | bộ đầy đủ không kịp NHƯNG sau khi **bỏ dần món chậm nhất** còn **≥ 3 món** kịp | Render phương án nhanh (giữ ≥1 item key); mô tả bộ đầy đủ để requester **dời deadline** lấy lại nguyên vẹn. |
| 🔴 **KHÔNG ĐỦ → điều chỉnh** (`adjust`) | sau khi bỏ bớt vẫn < 3 món kịp | Hỏi dời deadline; mốc trung thực = **sàn món nhanh nhất toàn kho**. |

(Hệ số 1.15 = `DEADLINE_BUFFER`; ngưỡng 3 món = `MIN_FAST_ITEMS`.)

## 5. Nội dung lõi — chọn item ("suggest từ đâu?")

Agent chọn theo **2 trục độc lập**:
- **Relevance** (AI chọn món hợp game/đối tượng) — phán đoán ngữ nghĩa.
- **Feasibility** (code tính tiền + thời gian) — xác định.

**4 nguồn của relevance:**
1. **Đề bài** requester (Game, Mục đích, Chủ đề, Định vị, Target, Số lượng, Deadline, Budget, Yêu cầu đặc biệt).
2. **Mô tả kho hàng** (text — KHÔNG đưa ảnh vào AI).
3. **Insight game** — Agent **tra Google** về game để định hướng đối tượng/phong cách (giảm phụ thuộc kho).
4. **Phân khúc giá** = Budget ÷ Số lượng mỗi bộ → quyết "đẳng cấp" món.

> **Nói thẳng (transparency):** việc chọn là **phán đoán ngữ nghĩa của AI, CHƯA có dữ liệu doanh số / lịch sử bán**. Đó là lý do cần requester & leader góp ý để cải thiện. (🟡)

**Quy tắc cơ cấu:**
- **Catalogue-first** (có giá thật, nhanh); **creative chỉ lấp** món kho thiếu → có thể **0 creative** (hợp lệ).
- **Số creative ≤ số catalogue** (giữ đa số có giá để chốt được).
- **≥ 1 item key ⭐** (điểm nhấn).
- Số item linh hoạt **3–6**, chất hơn lượng.
- **MOQ**: Số lượng đề bài < số lượng tối thiểu của món → tự nâng lên MOQ + ghi chú.

**Phân khúc giá (`value_tier`):**
| Ngân sách/bộ (= Budget÷SL) | Phân khúc | Hướng chọn |
|---|---|---|
| < {{TIER_LOW}}đ | Phổ thông | Món thực dụng, có thể nhiều món |
| {{TIER_LOW}} – {{TIER_HIGH}}đ | Tầm trung | Cân bằng giá trị/thẩm mỹ |
| > {{TIER_HIGH}}đ | Cao cấp | Item giá trị/thẩm mỹ cao, xứng VIP |

## 6. Nội dung — ngân sách & giá

- Tổng (đơn giá × số lượng, **bỏ qua món chưa có giá**) **≤ Budget**.
- Vượt budget → AI tự điều chỉnh **≤ 2 vòng**; vẫn vượt → chuyển vòng điều chỉnh (nhắc gọn, không đi sâu vận hành).
- **Khi nào "confirm" được giá:**
  - **Catalogue** → ✅ giá kho **cố định** (code ép theo bảng, chống AI bịa).
  - **Creative** → 🟡 **để trống có chủ đích**, chờ báo giá vendor sau khi có design (KHÔNG bịa).

## 7. Nội dung — yêu cầu đặc biệt

- Requester ghi yêu cầu đặc biệt = ràng buộc bắt buộc. AI chấm từng cái **met/unmet**.
- **Design có sẵn** (requester đưa link) → **luôn met** (giá null, hỏi vendor sau).
- Có unmet → Agent hỏi lại, không tự nhận bừa.

## 8. Ví dụ xuyên suốt (1 dự án thật, chia case theo mục)

> **Dự án mẫu:** quà sự kiện game **Infinity Nikki** · **500 bộ** · **Budget 150.000.000đ** → 300.000đ/bộ = **Tầm trung**.

- **§5 chọn item** — bộ mẫu: Áo thun (catalogue, 120k×500=60tr) · Bình giữ nhiệt (catalogue, 90k×500=45tr) · Sổ tay (catalogue, 50k×500=25tr) · ⭐ Figure nhân vật (creative, giá null). Nguồn: Nikki = game thời trang nữ (insight web) → ưu tiên phụ kiện thẩm mỹ; phân khúc Tầm trung.
- **§6 ngân sách** — tổng có giá 130tr ≤ 150tr ✅ (dư ~20tr cho creative). Catalogue confirm giá; Figure creative chờ vendor.
- **§5 MOQ** — nếu Bình giữ nhiệt có MOQ 1000 mà requester cần 500 → Agent nâng lên 1000 + cảnh báo ảnh hưởng tổng.
- **§4 deadline (3 case, cùng bộ có Figure creative → cần 84 ngày):**
  - **ĐỦ**: còn 110 ngày ≥ 84 → ra bộ đầy đủ.
  - **GẤP**: còn 78 ngày → bộ 84 ngày không kịp; bỏ Figure (chậm nhất) còn 3 món catalogue (74 ngày) kịp → phương án nhanh + mời dời deadline lấy lại Figure.
  - **KHÔNG ĐỦ**: còn 48 ngày → cả món nhanh nhất toàn kho (sàn ~74 ngày nếu kho chưa điền lead-time) cũng trễ → hỏi dời deadline, báo "cần tối thiểu ~74 ngày".

> Các số ví dụ là minh hoạ; số ngưỡng/giả định (27, ×1.4, 8/25, phân khúc) chèn từ config nên luôn khớp hệ thống.

## 9. Cấu trúc trang (sections, theo thứ tự render)

1. **Header** + dòng giải thích 2 trục + ghi chú nhãn ✅/🟡.
2. **Proposal là gì** — 2 trục Relevance vs Feasibility.
3. **Thẻ "Dự án mẫu"** — bộ số §8.
4. **⭐ "Tại sao cần ~X ngày?"** — Gantt 17 bước (SVG) → công thức gom (27 + lên mẫu + sản xuất)×1.4 → bảng 74 vs 84 → 3 kết cục (§4) trên dự án mẫu → callout 🟡 + insight "vì sao hay không kịp".
5. **⭐ "Items suggest từ đâu?"** — 4 nguồn + tuyên bố "chưa có dữ liệu doanh số" + quy tắc cơ cấu + phân khúc (§5).
6. **Ngân sách & giá** (§6).
7. **Yêu cầu đặc biệt** (§7).
8. **Độ chính xác** — bảng tổng ✅/🟡 mọi con số + lời hứa "luôn nói rõ cần ~X / còn Y ngày".

## 10. Gantt 17 bước (dữ liệu để dựng SVG — VERIFY khi review)

Tái hiện từ ảnh user cung cấp + số config. Đơn vị = ngày làm việc (LV) kể từ ngày submit. Phân loại: **C** = critical path · **P** = song song/ngoài critical · **R** = nhánh riêng/định kỳ.

| # | Bước | Bắt đầu (LV) | Dài (LV) | Loại | Ghi chú |
|---|---|---|---|---|---|
| 1 | Intake — Nhận request | 0 | 1 | C | |
| 2 | Proposal items | 1 | 7 | C | |
| 3 | Báo giá dự kiến | 8 | 3 | P | song song với 5 |
| 4 | Planning budget | 11 | 2 | P | gối lên 3 |
| 5 | Design + Mockup | 8 | 8 | C | song song với 3–4 |
| 6 | Phân tích vật liệu | 16 | 2 | P | gối lên 5 theo item |
| 7 | Plan final + Eform | 16 | 3 | P | song song với 9–10 |
| 8 | PR mua hàng | 19 | 5 | P | song song với 10–11 |
| 9 | Vendor báo giá final | 16 | 3 | P | song song với 7 |
| 10 | Lên mẫu | 16 | 8 | C | bắt đầu cùng bước 7 |
| 11 | Duyệt mẫu | 24 | 7 | C | lặp theo round |
| 12 | Chọn vendor + PO + Legal | 31 | 4 | P | song song 13, hội tụ MAX(8,9,11) |
| 13 | Sản xuất hàng loạt (*) | 33 | 18 | C | (*) tuỳ item |
| 14 | Giao hàng nhập kho | 51 | 2 | C | |
| 15 | Thanh toán vendor | 53 | 2 | P | ngoài critical |
| 16 | Branding plan bộ merch | 33 | 7 | R | sau duyệt mẫu, nhánh riêng |
| 17 | Report định kỳ | 0 | 60 | R | định kỳ, ngoài pipeline đơn hàng |

- Vạch mốc: **Nhanh nhất 31 LV (~6 tuần) · Trung bình 53 LV (~10,5 tuần) · Chậm nhất 68 LV (~13,5 tuần)** — khớp `PIPELINE_WORKDAYS {min:31, avg:53, max:68}`. Vạch đỏ ở 53.
- **Mapping Gantt → công thức:** OVERHEAD 27 = Head 18 (gói các bước đầu trước Lên mẫu) + Duyệt mẫu 7 (bước 11) + Giao 2 (bước 14); + Lên mẫu (bước 10) + Sản xuất (bước 13). Trang nói rõ "Agent gom 17 bước thành công thức này".
- SVG **nội tuyến** (self-contained, không thư viện ngoài), responsive theo `viewBox`; chú giải 4 loại như ảnh.

## 11. Tích hợp

- Thêm `("/proposal", "🧾 Proposal")` vào `_DOC_NAV_ITEMS` (main.py) → nav tự xuất hiện trên cả 5 trang (tạm thời 5 trang).
- Route `GET /proposal` → `_serve_doc("proposal.html", "/proposal", subs={...})`.
- File mới `docs/proposal.html` (mượn CSS từ proposal-rules.html cho nhất quán: `.formula`, `.pill ok/warn/crit`, `table`, `.assum`…).
- **Placeholder `subs` (số từ config — đảm bảo khớp):**
  | Placeholder | Nguồn config |
  |---|---|
  | `{{OVERHEAD}}` | `DEADLINE_OVERHEAD_WORKDAYS` (27) |
  | `{{OVERHEAD_HEAD}}` `{{OVERHEAD_REVIEW}}` `{{OVERHEAD_DELIVERY}}` | 18 / 7 / 2 |
  | `{{WD2CAL}}` | `WORKDAYS_TO_CALENDAR` (1.4) |
  | `{{CREATIVE_LM}}` `{{CREATIVE_SX}}` | 8 / 25 |
  | `{{GENERIC_LM}}` `{{GENERIC_SX}}` | 8 / 18 (fallback) |
  | `{{DAYS_FULL}}` `{{DAYS_CAT}}` | tính sẵn 84 / 74 (hoặc compute trong route) |
  | `{{TIER_LOW}}` `{{TIER_HIGH}}` | 100.000 / 500.000 |
  | `{{MIN_FAST}}` | `MIN_FAST_ITEMS` (3) |
  | `{{BUFFER}}` | `DEADLINE_BUFFER` (1.15) |
  | `{{PWD_MIN}}` `{{PWD_AVG}}` `{{PWD_MAX}}` | `PIPELINE_WORKDAYS` 31/53/68 |

## 12. Test

`tests/test_proposal_page.py` (TestClient, theo mẫu `test_guide_page.py`):
- `GET /proposal` → 200.
- **REQUIRED**: các số thật phải xuất hiện sau render: `74`, `84`, `27`, `1.4`, `8`, `25`, `100.000`/`500.000`, `31`, `53`, `68`, nhãn ✅/🟡, "Relevance", "Feasibility", "Infinity Nikki" — lưới chống bịa/sót (đổi số trong config thì test bắt cập nhật trang).
- **Không còn placeholder**: assert `{{` không xuất hiện trong HTML đã serve.
- **FORBIDDEN**: không chứa `bạn`/`Bạn`; không lộ tên env var/field (vd `fld`, `MAX_PROPOSAL_ROUNDS`, `config.py`).
- Cập nhật `test_shared_nav_on_all_doc_pages` (nếu có) để gồm `/proposal`.
- Chạy: `venv/bin/python -m pytest tests/ -q`.

## 13. Hạng mục cần VERIFY khi review

1. Số liệu Gantt §10 (start/dài/loại) có khớp ảnh gốc không.
2. Bộ số dự án mẫu §8 (giá item Nikki) — hợp lý/đúng kho không.
3. Xác nhận `{{DAYS_FULL}}`/`{{DAYS_CAT}}` = 84/74 đúng (round((27+8+25)×1.4)=84; round((27+8+18)×1.4)=74).
4. Có muốn trang nêu thẳng số "136/56" của `/rules` là sai để tránh nhầm, hay chỉ âm thầm dùng số đúng.

## 14. Không làm (YAGNI)

- KHÔNG xoá `/rules` trong spec này (làm sau khi `/proposal` được duyệt đủ).
- KHÔNG hiệu chỉnh công thức deadline (task riêng, cần data thật).
- KHÔNG thêm vòng duyệt/PIC/hạn duyệt vào trang.
- KHÔNG generate ảnh/asset động — trang tĩnh thuần.
