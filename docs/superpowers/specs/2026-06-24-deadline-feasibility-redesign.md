# Spec — Thiết kế lại nhánh Deadline (feasibility + relevance)

Ngày: 2026-06-24 · Module: `proposal.py`, `pipeline.py`, `proposal_render.py`, Airtable (Projects + Fillout)

## 1. Bối cảnh & vấn đề (đã xác minh trong code)

Hiện `propose_items_for` → `_resolve_deadline` ([proposal.py]) có 4 lỗ hổng:

1. **Verdict "không khả thi" KHÔNG trung thực.** Code chỉ xét catalogue **trong proposal LLM vừa chọn** (`cats = [it for it in proposal items if nguon=="catalogue"]`), nhưng message gửi requester ghi *"cần ~X ngày kể cả hàng có sẵn **nhanh nhất**"* — sai sự thật. Nếu LLM chọn món catalogue chậm, hoặc chọn 0 catalogue → tuyên infeasible dù kho vẫn có món làm kịp ⇒ **dương tính giả**.
2. **Khi infeasible → return sớm, KHÔNG có proposal nào** để requester xem ⇒ requester không đánh giá được item có hợp nhu cầu không, không thấy phương án thay thế.
3. **Không cân nhắc relevance** khi nói tới "hàng có sẵn nhanh" — nhanh mà không hợp game/đối tượng (vd Nikki nữ tính mà gợi món cho nam) thì vô dụng.
4. **Độ chính xác chưa đo được** — hằng số `[GIẢ ĐỊNH]` (overhead 27 LV, ×1.4, creative 8/25, catalogue fallback 8/18) chưa validate dữ liệu thật.

## 2. Mục tiêu

- Verdict feasibility **trung thực**: chỉ tuyên "không kịp dù chọn gì" khi cả món nhanh nhất TOÀN KHO cũng trễ.
- Khi bộ lý tưởng không kịp nhưng có **phương án nhanh vừa hợp vừa kịp** → render phương án nhanh (cụ thể) + **mô tả** bộ đầy đủ + cho requester chọn.
- **Consistency**: requester dời deadline để lấy bộ đầy đủ → **restore ĐÚNG bộ đã mô tả từ snapshot, KHÔNG re-roll**.
- **Relevance được giữ**: không bao giờ chọn item theo tốc độ thuần.
- **Minh bạch số liệu** để xây lòng tin.

## 3. Nguyên tắc phân chia trách nhiệm

| Thành phần | Việc |
|---|---|
| **LLM** (giữ nguyên) | Chọn **bộ lý tưởng hợp game/đối tượng** (relevance/quality). |
| **Code** (deterministic) | Floor toàn kho · tách fast/slow theo lead-time · snapshot · verdict · restore. |

**Insight cốt lõi (giải bài toán Nikki):** `fast = (bộ LLM chọn) ∩ (kịp deadline)` — fast subset **luôn là tập con của bộ relevant**, nên luôn hợp nhu cầu. Ta KHÔNG pull món nhanh-nhưng-không-liên-quan từ kho.

## 4. Thiết kế chi tiết

### 4.1 Data (Airtable Projects)
- **MỚI**: field hidden `Phương án đầy đủ (JSON)` (multilineText) — snapshot bộ đầy đủ (full schema item: ten/nguon/loai/chat_lieu/kich_thuoc/so_luong/don_gia/can_cu_gia/item_key/design_link/goi_y_anh) khi deadline gấp. Rỗng = không có phương án treo.
- Tái dùng `Proposal JSON` cho bộ đang publish (như hiện tại).

### 4.2 Hàm mới / sửa trong `proposal.py`

**`catalogue_floor_days(by_name) -> int`** (mới):
```
min trên MỌI item catalogue của (DEADLINE_OVERHEAD_WORKDAYS + lm + sx) × WORKDAYS_TO_CALENDAR
```
= sàn tuyệt đối (1 món nhanh nhất; bộ lấy max nên ≥ sàn này). Trả kèm tên món nhanh nhất (cho message).

**`_fit_within_deadline(items, by_name, days_left) -> (fast, slow)`** (mới):
- Greedy: `keep = list(items)`; trong khi `deadline_days_needed(keep) > days_left`: bỏ item có `(lm+sx)` lớn nhất khỏi `keep`. Kết thúc → `fast=keep`, `slow=phần bị bỏ`.
- (Bộ song song → need = overhead + max(lm) + max(sx); bỏ dần món chậm nhất là đúng & đơn giản.)

**`_resolve_deadline(...)` (viết lại)** — trả 1 trong 3 kết cục:
```
days_left = days_to_deadline_of(fields)
if days_left is None: return ("", None, None)            # không có deadline → bỏ qua (như cũ)
needed_full = deadline_days_needed(full_items)
if needed_full <= days_left:                             # bộ đầy đủ kịp
    warn = "⚠️ sát" nếu days_left < needed_full*BUFFER else ""
    return (warn, None, None)                            # publish bộ đầy đủ bình thường
# --- bộ đầy đủ KHÔNG kịp ---
fast, slow = _fit_within_deadline(full_items, days_left)
fast_viable = len(fast) >= MIN_FAST_ITEMS                # (đảm bảo ≥1 item_key: promote món fast đầu nếu thiếu)
if fast_viable:
    return ("FAST", {fast, full_snapshot, slow, needed_full, days_left})
else:
    floor, floor_name = catalogue_floor_days(by_name)
    return ("ADJUST", {full_snapshot, needed_full, days_left, floor, floor_name, fast})
```

**Hằng số** (config.py): `MIN_FAST_ITEMS = 3`.

### 4.3 `propose_items_for` — contract kết quả (bổ sung)
Sau budget gate, gọi `_resolve_deadline`. Map:
- **(none)** bộ đầy đủ kịp → publish bộ đầy đủ (như hiện tại). `Cảnh báo deadline` = warn (⚠️ sát) nếu có.
- **FAST** → result `{"deadline_fast": True, "items"=fast, "full_snapshot"=[...], "upgrade":{slow, needed_full}, ...}`. (Đã tạo Items = fast; lưu snapshot.)
- **ADJUST** → result `{"adjust_deadline": True, "full_snapshot"=[...], "needed": needed_full, "days_left", "floor", "floor_name", "fast"}`. KHÔNG tạo Items.

### 4.4 `pipeline.py` — routing & restore

**`_route_result`** thêm 2 nhánh:
- `result["deadline_fast"]` → `_publish_proposal(...)` bộ fast NHƯ thường + ghi `Phương án đầy đủ (JSON)` = full_snapshot + `Cảnh báo deadline` = mô tả nâng cấp (xem 4.5). Status `Chờ duyệt items`.
- `result["adjust_deadline"]` → `_enter_adjust_deadline(...)` (đã có) nhưng message mới (4.5) + ghi `Phương án đầy đủ (JSON)` = full_snapshot. Status `Chờ điều chỉnh`.

**Restore từ snapshot** (mới) — dùng CHUNG cho 2 nhánh quyết định:
- Trong `_scan_decisions` tại Status `Chờ duyệt items` **và** trong `_reevaluate_adjust` tại `Chờ điều chỉnh`, thêm precedence:
  ```
  1. Cần sửa + feedback                         → _revise (re-roll @ deadline mới); clear snapshot
  2. else snapshot≠rỗng & days_left ≥ deadline_days_needed(snapshot)
                                                → _publish_from_snapshot (KHÔNG LLM); clear snapshot
  3. else Duyệt (chỉ ở Chờ duyệt items)          → _approve_proposal (chốt fast)
  4. else (dời chưa đủ / thiếu decision)         → message "cần ≥ Z, hiện {days_left}"; giữ nguyên
  ```
- **`_publish_from_snapshot(record_id, items)`** (mới): tạo Items từ `items` (tái dùng `_build_item_records`), render HTML (`build_proposal_html` + `_build_images` — ảnh creative qua cache), `upload_proposal`, set Status `Chờ duyệt items` + `Proposal JSON`=items + clear `Phương án đầy đủ (JSON)`. **Không gọi LLM** → consistency tuyệt đối.

> Lưu ý: bộ đầy đủ trong snapshot đã qua `_enforce_catalogue_price` + budget gate lúc tạo → restore không cần re-validate budget. Deadline đã check ≥ Z trước khi restore.

### 4.5 `proposal_render.py` + message (UX)

**FAST proposal (HTML + email body):**
- Render items = fast (như thường).
- Thêm khối "💡 Phương án đầy đủ": *"Để hợp game hơn, có thể thêm: [tên slow items]. Cần dời 'Deadline cần hàng' tới ≥ {ngày tương ứng needed_full} rồi gửi lại."*
- `Cảnh báo deadline` = *"✅ Phương án nhanh kịp deadline {hiện tại}. 💡 Bộ đầy đủ (thêm [..]) cần dời tới ≥ {Z}."*

**ADJUST message (`Trao đổi yêu cầu`):**
- Tier hard (floor): *"Deadline còn {days_left} ngày — không kịp dù chọn món NHANH NHẤT trong kho ([floor_name], tối thiểu ~{floor} ngày). Vui lòng dời 'Deadline cần hàng' tới ≥ ~{needed} (cho bộ đề xuất) rồi gửi phản hồi."*
- Tier fast-yếu: *"Các món phù hợp game/đối tượng đều cần thời gian; phương án nhanh chưa đủ phong phú. Bộ đề xuất gồm [tên] cần ≥ {needed} ngày — vui lòng dời 'Deadline cần hàng' tới ≥ {ngày} rồi gửi phản hồi."*

**Minh bạch (mọi message/banner deadline):** kèm breakdown + nhãn ước tính:
> *"Cần ~{needed} ngày = {overhead} chuẩn bị + ~{max lên mẫu} lên mẫu + ~{max sản xuất} sản xuất (×1.4 ra lịch). (Ước tính theo lead-time catalogue.)"*

### 4.6 Fillout (UI) — thay đổi
- Section Status `Chờ duyệt items`: **thêm field `Deadline cần hàng`** (prefill ngày hiện tại), **conditional hiện chỉ khi `Phương án đầy đủ (JSON)` ≠ rỗng**, helper text *"Muốn bộ đầy đủ? Dời ngày này ≥ {Z}"*.
- Section `Chờ điều chỉnh`: đã có sửa Deadline (giữ nguyên).
- Giữ nguyên Quyết định [Duyệt/Cần sửa] + Góp ý conditional.

## 5. User flow (chốt)

```
Deadline gấp:
  ├─ fast viable  → render FAST (Chờ duyệt items) + snapshot full + mô tả nâng cấp
  │     requester:
  │       • Duyệt                         → chốt fast → Đã duyệt items + plan
  │       • dời Deadline ≥ Z (Fillout)    → restore full (no re-roll) → Chờ duyệt items → Duyệt
  │       • Cần sửa + feedback            → revise (re-roll @ deadline mới)
  └─ fast KHÔNG viable → ADJUST (Chờ điều chỉnh) + snapshot full + message honest(floor/breakdown)
        requester:
          • dời Deadline ≥ Z             → restore full → Chờ duyệt items → Duyệt
          • Cần sửa + feedback            → revise
          • dời chưa đủ                   → báo cần ≥ Z
```

## 6. Edge cases
- Dời deadline nhưng `< Z` → message "cần ≥ Z, hiện {days_left}", giữ trạng thái.
- Cần sửa + đồng thời dời deadline → **revise thắng** (re-roll @ deadline mới), bỏ snapshot.
- Restore xong → clear `Phương án đầy đủ (JSON)` (tránh restore lặp).
- Duyệt fast (không lấy full) → clear snapshot khi chốt.
- Không có deadline (rỗng) → bỏ qua nhánh (như cũ).
- `days_left ≥ floor` nhưng LLM chọn toàn creative/slow → fast rỗng → ADJUST (fast-yếu), KHÔNG nhồi món lạ.

## 7. Phạm vi KHÔNG đụng (giữ nguyên)
- Bước 1 (analyze) generic deadline warning — vẫn giữ (chỉ cảnh báo, không chặn).
- Budget gate, MOQ, clarify yêu cầu đặc biệt, revise minimal-diff (`giu_nguyen`).
- LLM prompt chọn item (relevance) — **không** nhồi ràng buộc deadline vào prompt (code lo feasibility).
  - *Bỏ* khối prompt cũ "DEADLINE KHÔNG KHẢ THI → chỉ catalogue" (Bước-1 based) vì code xử lý chính xác hơn.

## 8. Testing (đưa vào Qase suite "Bước 2 — Deadline")
- Floor honest: deadline < floor toàn kho → ADJUST tier-hard, message nêu món nhanh nhất + floor.
- FAST viable: deadline gấp, bộ lý tưởng có ≥3 catalogue kịp → render fast + snapshot + mô tả nâng cấp.
- Restore consistency: từ FAST, dời deadline ≥ Z → items ĐÚNG snapshot (so khớp tên/giá), KHÔNG re-roll.
- Fast-yếu: relevant items đều chậm → ADJUST, không nhồi món lạ.
- Cần sửa + dời deadline → revise thắng.
- Dời chưa đủ Z → message cần ≥ Z.
- Regression: deadline ổn → publish bộ đầy đủ như cũ; ⚠️ sát vẫn cảnh báo.

## 9. Follow-up NON-CODE (để đạt độ tin 70-80%)
- Validate hằng số (overhead 27 / ×1.4 / creative 8-25 / catalogue lead-time text) với 10-15 dự án thật → hiệu chỉnh; trước đó giữ nhãn "ước tính".
- Cập nhật Qase + memory test-cases sau khi implement.
</content>
